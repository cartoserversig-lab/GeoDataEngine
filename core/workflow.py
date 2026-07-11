"""Orchestration de la chaine de traitement (acquisition, harmonisation, organisation)."""

from __future__ import annotations

import logging
from pathlib import Path

from processing.reprojection import ReprojectionError, reproject_to_target_crs
from processing.validation import check_all_vector_layers, check_crs_consistency

logger = logging.getLogger(__name__)

# Repertoire de donnees par defaut : data/ a la racine du depot.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def run_quality_checks(
    data_dir: str | Path = DEFAULT_DATA_DIR, auto_reproject: bool = False
) -> None:
    """Etape "Controle qualite" du pipeline (CDC section 5.1), puis "Reprojection".

    Verifie que chaque fichier vecteur, raster ou lidar sous data_dir est
    dans le CRS attendu du projet (core.config.TARGET_CRS), et que chaque
    couche vectorielle a un systeme de coordonnees identifie, des
    geometries valides et non vides, et des coordonnees dans une emprise
    plausible (coherence spatiale).

    Si auto_reproject est True, les fichiers vecteur/raster non conformes
    au CRS attendu sont automatiquement reprojetes (etape "Reprojection"
    du CDC), puis le controle CRS est relance. Sinon, une erreur est levee
    listant les fichiers en cause. Le lidar (.laz/.las) n'est pas
    reprojete automatiquement.

    Toute erreur geometrique detectee leve egalement une erreur : ces
    problemes ne peuvent pas etre corriges automatiquement.
    """
    crs_issues = check_crs_consistency(data_dir)

    if crs_issues and auto_reproject:
        for issue in crs_issues:
            if issue.couche is not None:
                # Fichier multi-couches (ex : projet.gpkg, base compilee) : la
                # reprojection en place ecraserait les autres couches, on ne
                # la tente pas automatiquement.
                logger.warning(
                    "Reprojection automatique ignoree pour %s::%s (fichier multi-couches).",
                    issue.fichier,
                    issue.couche,
                )
                continue
            try:
                reproject_to_target_crs(issue.fichier)
            except ReprojectionError:
                logger.warning("Reprojection non prise en charge pour %s.", issue.fichier)

        crs_issues = check_crs_consistency(data_dir)

    if crs_issues:
        details = "\n".join(
            f"  - {issue.fichier}"
            + (f"::{issue.couche}" if issue.couche else "")
            + f" : {issue.crs_trouve} (attendu {issue.crs_attendu})"
            for issue in crs_issues
        )
        raise ValueError(f"Incoherence de CRS detectee :\n{details}")

    geometry_issues = check_all_vector_layers(data_dir)

    if geometry_issues:
        details = "\n".join(
            f"  - {key} : {issue.probleme}"
            for key, issues in geometry_issues.items()
            for issue in issues
        )
        raise ValueError(f"Problemes geometriques detectes :\n{details}")

    logger.info("Controle qualite : OK, aucune incoherence CRS ni geometrique detectee.")
