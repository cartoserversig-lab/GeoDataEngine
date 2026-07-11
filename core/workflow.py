"""Orchestration de la chaine de traitement (acquisition, harmonisation, organisation)."""

from __future__ import annotations

import logging
from pathlib import Path

from processing.validation import check_crs_consistency

logger = logging.getLogger(__name__)

# Repertoire de donnees par defaut : data/ a la racine du depot.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def run_quality_checks(data_dir: str | Path = DEFAULT_DATA_DIR) -> None:
    """Etape "Controle qualite" du pipeline : verifie la coherence des CRS.

    Parcourt data_dir et leve une erreur si un fichier vecteur, raster ou
    lidar n'est pas dans le CRS attendu du projet (core.config.TARGET_CRS).
    """
    issues = check_crs_consistency(data_dir)

    if issues:
        details = "\n".join(
            f"  - {issue.fichier} : {issue.crs_trouve} (attendu {issue.crs_attendu})"
            for issue in issues
        )
        raise ValueError(f"Incoherence de CRS detectee :\n{details}")

    logger.info("Controle qualite CRS : OK, aucune incoherence detectee.")
