"""Fenetre principale de l'interface desktop GeoData Engine (PySide6)."""

from __future__ import annotations

import csv
import logging
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import load_settings
from core.workflow import DEFAULT_DATA_DIR
from interface.desktop.logging_bridge import QtLogEmitter, QtLogHandler
from interface.desktop.worker import PipelineWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Fenetre principale : formulaire d'emprise + options, suivi d'execution.

    Reprend exactement les parametres deja exposes par main.py (CLI), sous
    forme de formulaire : nom/code INSEE/bbox de l'entite (au lieu d'un CSV
    a editer a la main), dossier de sortie, buffers, options Lidar/ortho.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GeoData Engine")
        self.resize(760, 680)

        self._settings = load_settings()
        self._worker: PipelineWorker | None = None
        self._temp_csv_path: Path | None = None

        self._build_ui()
        self._setup_logging()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        form = QFormLayout()

        self.nom_edit = QLineEdit()
        self.nom_edit.setPlaceholderText("Ruy-Montceau")
        form.addRow("Nom de l'entite", self.nom_edit)

        self.code_insee_edit = QLineEdit()
        self.code_insee_edit.setPlaceholderText("38348")
        form.addRow("Code INSEE", self.code_insee_edit)

        self.bbox_edit = QLineEdit()
        self.bbox_edit.setPlaceholderText(
            "[xmin,ymin,xmax,ymax] en EPSG:2154 (optionnel, calculee automatiquement sinon)"
        )
        form.addRow("Bbox (optionnelle)", self.bbox_edit)

        data_dir_row = QHBoxLayout()
        self.data_dir_edit = QLineEdit(str(DEFAULT_DATA_DIR))
        browse_button = QPushButton("Parcourir...")
        browse_button.clicked.connect(self._choose_data_dir)
        data_dir_row.addWidget(self.data_dir_edit)
        data_dir_row.addWidget(browse_button)
        form.addRow("Dossier de sortie (data/)", data_dir_row)

        self.buffer_decoupe_spin = QDoubleSpinBox()
        self.buffer_decoupe_spin.setRange(0, 10_000)
        self.buffer_decoupe_spin.setSuffix(" m")
        self.buffer_decoupe_spin.setValue(self._settings.buffer_decoupe)
        form.addRow("Buffer decoupage", self.buffer_decoupe_spin)

        self.buffer_telechargement_spin = QDoubleSpinBox()
        self.buffer_telechargement_spin.setRange(0, 10_000)
        self.buffer_telechargement_spin.setSuffix(" m")
        self.buffer_telechargement_spin.setValue(self._settings.buffer_telechargement)
        form.addRow("Buffer telechargement", self.buffer_telechargement_spin)

        layout.addLayout(form)

        self.include_lidar_check = QCheckBox("Telecharger et traiter le Lidar HD (volumineux)")
        self.include_lidar_check.setChecked(self._settings.include_lidar)
        self.include_lidar_check.toggled.connect(self._on_include_lidar_toggled)
        layout.addWidget(self.include_lidar_check)

        self.include_ortho_check = QCheckBox("Telecharger l'orthophotographie (volumineux)")
        self.include_ortho_check.setChecked(self._settings.include_ortho)
        layout.addWidget(self.include_ortho_check)

        self.auto_reproject_check = QCheckBox("Reprojection automatique lors du controle qualite")
        self.auto_reproject_check.setChecked(self._settings.auto_reproject)
        layout.addWidget(self.auto_reproject_check)

        self.classify_lidar_check = QCheckBox(
            "Classifier le nuage de points depuis les couches vecteur (couteux, voir notebook 20)"
        )
        self.classify_lidar_check.setChecked(self._settings.classify_lidar_from_vectors)
        self.classify_lidar_check.setEnabled(self.include_lidar_check.isChecked())
        layout.addWidget(self.classify_lidar_check)

        self.run_button = QPushButton("Lancer")
        self.run_button.clicked.connect(self._on_run_clicked)
        layout.addWidget(self.run_button)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: Consolas, monospace;")
        layout.addWidget(self.log_view, stretch=1)

        self.result_label = QLabel("")
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

    def _setup_logging(self) -> None:
        self._log_emitter = QtLogEmitter()
        self._log_emitter.message.connect(self.log_view.appendPlainText)

        handler = QtLogHandler(self._log_emitter)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    # ------------------------------------------------------------------
    # Actions utilisateur
    # ------------------------------------------------------------------
    def _choose_data_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Dossier de sortie", self.data_dir_edit.text())
        if chosen:
            self.data_dir_edit.setText(chosen)

    def _on_include_lidar_toggled(self, checked: bool) -> None:
        self.classify_lidar_check.setEnabled(checked)
        if not checked:
            self.classify_lidar_check.setChecked(False)

    def _on_run_clicked(self) -> None:
        nom = self.nom_edit.text().strip()
        code_insee = self.code_insee_edit.text().strip()

        if not nom or not code_insee:
            QMessageBox.warning(
                self, "Champs manquants", "Le nom de l'entite et le code INSEE sont obligatoires."
            )
            return

        try:
            csv_path = self._write_temp_csv(nom, code_insee, self.bbox_edit.text().strip())
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de creer le fichier d'entite temporaire : {exc}")
            return

        self.log_view.clear()
        self.result_label.setText("")
        self.run_button.setEnabled(False)
        self.run_button.setText("Traitement en cours...")

        self._worker = PipelineWorker(
            csv_path=csv_path,
            data_dir=Path(self.data_dir_edit.text().strip() or DEFAULT_DATA_DIR),
            clip_buffer=self.buffer_decoupe_spin.value(),
            download_buffer=self.buffer_telechargement_spin.value(),
            include_lidar=self.include_lidar_check.isChecked(),
            include_ortho=self.include_ortho_check.isChecked(),
            auto_reproject=self.auto_reproject_check.isChecked(),
            classify_lidar_from_vectors=self.classify_lidar_check.isChecked(),
        )
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _write_temp_csv(self, nom: str, code_insee: str, bbox: str) -> Path:
        # Reutilise le format CSV attendu par core.config.load_entities plutot
        # que de dupliquer la logique de construction d'une Entity : le
        # pipeline (run_pipeline) ne connait que ce chemin d'entree.
        fd, path_str = tempfile.mkstemp(suffix=".csv", prefix="geodataengine_entite_")
        path = Path(path_str)
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["nom_entite", "type_entite", "code_insee", "bbox"])
            writer.writerow([nom, "commune", code_insee, bbox])
        self._temp_csv_path = path
        return path

    # ------------------------------------------------------------------
    # Callbacks du worker
    # ------------------------------------------------------------------
    def _on_finished_ok(self, geopackage_path: str, filegdb_path: str) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("Lancer")
        self.result_label.setText(
            f"Projet SIG genere :\nGeoPackage : {geopackage_path}\nFile Geodatabase : {filegdb_path}"
        )
        self._cleanup_temp_csv()

    def _on_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("Lancer")
        QMessageBox.critical(self, "Echec du traitement", message)
        self._cleanup_temp_csv()

    def _cleanup_temp_csv(self) -> None:
        if self._temp_csv_path is not None:
            self._temp_csv_path.unlink(missing_ok=True)
            self._temp_csv_path = None

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(
                self, "Traitement en cours", "Un traitement est en cours ; attendez sa fin avant de fermer."
            )
            event.ignore()
            return
        event.accept()
