"""Orchestration de la chaine de traitement (acquisition, harmonisation, organisation)."""

from __future__ import annotations

import logging
from pathlib import Path

from processing.reprojection import ReprojectionError, reproject_to_target_crs
from processing.validation import check_crs_consistency

logger = logging.getLogger(__name__)

# Repertoire de donnees par defaut : data/ a la racine du depot.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def run_quality_checks(
    data_dir: str | Path = DEFAULT_DATA_DIR, auto_reproject: bool = False
) -> None:
    """Etapes "Controle qualite" puis "Reprojection" du pipeline.

    Parcourt data_dir et verifie que chaque fichier vecteur, raster ou lidar
    est dans le CRS attendu du projet (core.config.TARGET_CRS).

    Si auto_reproject est True, les fichiers vecteur/raster non conformes
    sont automatiquement reprojetes (etape "Reprojection" du CDC), puis le
    controle est relance. Sinon, une erreur est levee listant les fichiers
    en cause. Le lidar (.laz/.las) n'est pas reprojete automatiquement.
    """
    issues = check_crs_consistency(data_dir)

    if issues and auto_reproject:
        for issue in issues:
            try:
                reproject_to_target_crs(issue.fichier)
            except ReprojectionError:
                logger.warning("Reprojection non prise en charge pour %s.", issue.fichier)

        issues = check_crs_consistency(data_dir)

    if issues:
        details = "\n".join(
            f"  - {issue.fichier} : {issue.crs_trouve} (attendu {issue.crs_attendu})"
            for issue in issues
        )
        raise ValueError(f"Incoherence de CRS detectee :\n{details}")

    logger.info("Controle qualite CRS : OK, aucune incoherence detectee.")
