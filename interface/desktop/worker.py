"""Thread d'execution du pipeline GeoData Engine, pour ne pas geler l'interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.workflow import run_pipeline


class PipelineWorker(QThread):
    """Execute run_pipeline dans un thread separe et notifie le resultat par signal.

    run_pipeline peut prendre de quelques minutes (cas de base) a plusieurs
    heures (Lidar + classification vecteur active sur une commune entiere) :
    l'executer dans le thread de l'interface gelerait la fenetre.
    """

    finished_ok = Signal(str, str)  # (chemin_geopackage, chemin_filegdb)
    failed = Signal(str)

    def __init__(
        self,
        csv_path: Path,
        data_dir: Path,
        clip_buffer: float,
        download_buffer: float,
        include_lidar: bool,
        include_ortho: bool,
        auto_reproject: bool,
        classify_lidar_from_vectors: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.csv_path = csv_path
        self.data_dir = data_dir
        self.clip_buffer = clip_buffer
        self.download_buffer = download_buffer
        self.include_lidar = include_lidar
        self.include_ortho = include_ortho
        self.auto_reproject = auto_reproject
        self.classify_lidar_from_vectors = classify_lidar_from_vectors

    def run(self) -> None:
        try:
            geopackage_path, filegdb_path = run_pipeline(
                csv_path=self.csv_path,
                data_dir=self.data_dir,
                clip_buffer=self.clip_buffer,
                download_buffer=self.download_buffer,
                include_lidar=self.include_lidar,
                include_ortho=self.include_ortho,
                auto_reproject=self.auto_reproject,
                classify_lidar_from_vectors=self.classify_lidar_from_vectors,
            )
        except Exception as exc:  # remonte toute erreur du pipeline a l'interface plutot que de planter le thread
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(str(geopackage_path), str(filegdb_path))
