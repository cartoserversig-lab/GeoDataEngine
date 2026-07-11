"""Connecteur de recuperation des limites administratives (IGN ADMIN EXPRESS) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"
COMMUNE_TYPENAME = "ADMINEXPRESS-COG.LATEST:commune"
CODE_INSEE_FIELD = "code_insee"

# Repertoire de sortie par defaut : data/vector/limites_administratives a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "vector" / "limites_administratives"


class LimitesAdministrativesError(RuntimeError):
    """Erreur lors de la recuperation des limites administratives."""


def fetch_commune_boundary(
    code_insee: str, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Recupere la limite officielle (ADMIN EXPRESS IGN) de la commune correspondant a code_insee.

    La bbox sert a restreindre la requete WFS (doit contenir la commune) ; le
    resultat est ensuite filtre sur le code INSEE exact, car la bbox peut
    intersecter des communes voisines.
    """
    communes = fetch_wfs_features(WFS_URL, COMMUNE_TYPENAME, bbox, TARGET_CRS)
    match = communes[communes[CODE_INSEE_FIELD] == code_insee]

    if match.empty:
        raise LimitesAdministrativesError(
            f"Aucune commune trouvee pour le code INSEE {code_insee!r} sur cette emprise."
        )

    return match.reset_index(drop=True)


def download_commune_boundary(
    code_insee: str,
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    filename: str | None = None,
) -> Path:
    """Recupere la limite communale et l'ecrit en GeoPackage.

    Retourne le chemin du fichier GeoPackage ecrit.
    """
    boundary = fetch_commune_boundary(code_insee, bbox)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (filename or f"commune_{code_insee}.gpkg")
    boundary.to_file(output_path, driver="GPKG")
    logger.info("Limite communale de %s ecrite dans %s", code_insee, output_path)

    record_layer_metadata(
        layer=f"limite_communale_{code_insee}",
        source="ADMIN EXPRESS (IGN)",
        producteur="IGN",
        fichier=output_path,
        crs=TARGET_CRS,
    )

    return output_path
