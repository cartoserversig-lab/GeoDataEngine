"""Connecteur de telechargement des parcelles cadastrales (IGN Parcellaire Express) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"
PARCELLE_TYPENAME = "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle"
CODE_INSEE_FIELD = "code_insee"

# Repertoire de sortie par defaut : data/vector/cadastre a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "vector" / "cadastre"


class CadastreError(RuntimeError):
    """Erreur lors de la recuperation des parcelles cadastrales."""


def fetch_parcelles(
    code_insee: str, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Recupere les parcelles cadastrales (Parcellaire Express IGN) de la commune.

    La bbox restreint la requete WFS (doit contenir la commune) ; le
    resultat est ensuite filtre sur le code INSEE exact, car la bbox peut
    intersecter des communes voisines.
    """
    parcelles = fetch_wfs_features(WFS_URL, PARCELLE_TYPENAME, bbox, TARGET_CRS)
    match = parcelles[parcelles[CODE_INSEE_FIELD] == code_insee].reset_index(drop=True)

    if match.empty:
        raise CadastreError(f"Aucune parcelle cadastrale trouvee pour le code INSEE {code_insee!r}.")

    return match


def download_cadastre(
    code_insee: str,
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    filename: str | None = None,
) -> Path:
    """Recupere les parcelles cadastrales de la commune et les ecrit en GeoPackage.

    Retourne le chemin du fichier GeoPackage ecrit.
    """
    parcelles = fetch_parcelles(code_insee, bbox)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (filename or f"parcelles_{code_insee}.gpkg")
    parcelles.to_file(output_path, driver="GPKG")
    logger.info("%d parcelles cadastrales ecrites dans %s", len(parcelles), output_path)

    record_layer_metadata(
        layer=f"cadastre_parcelles_{code_insee}",
        source="Parcellaire Express (IGN)",
        producteur="IGN / DGFiP",
        fichier=output_path,
        crs=TARGET_CRS,
    )

    return output_path
