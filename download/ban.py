"""Connecteur de telechargement de la Base Adresse Nationale (BAN) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"
BAN_TYPENAME = "BAN.DATA.GOUV:ban"
CODE_INSEE_FIELD = "code_insee"

# Repertoire de sortie par defaut : data/raw/vector/adresses a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "vector" / "adresses"


class BanError(RuntimeError):
    """Erreur lors de l'interrogation de la Base Adresse Nationale."""


def fetch_ban_addresses(
    code_insee: str, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Recupere les adresses BAN de la commune correspondant a code_insee.

    La bbox restreint la requete WFS (doit contenir la commune) ; le
    resultat est ensuite filtre sur le code INSEE exact, car la bbox peut
    intersecter des communes voisines.
    """
    addresses = fetch_wfs_features(WFS_URL, BAN_TYPENAME, bbox, TARGET_CRS)
    match = addresses[addresses[CODE_INSEE_FIELD] == code_insee].reset_index(drop=True)

    if match.empty:
        raise BanError(f"Aucune adresse BAN trouvee pour le code INSEE {code_insee!r}.")

    return match


def download_ban(
    code_insee: str,
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    filename: str | None = None,
) -> Path:
    """Recupere les adresses BAN de la commune et les ecrit en GeoPackage.

    Retourne le chemin du fichier GeoPackage ecrit.
    """
    addresses = fetch_ban_addresses(code_insee, bbox)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (filename or f"adresses_{code_insee}.gpkg")
    addresses.to_file(output_path, driver="GPKG")
    logger.info("%d adresses BAN ecrites dans %s", len(addresses), output_path)

    record_layer_metadata(
        layer=f"ban_adresses_{code_insee}",
        source="Base Adresse Nationale (BAN)",
        producteur="IGN / DGFiP / La Poste / Etalab (BAN)",
        fichier=output_path,
        crs=TARGET_CRS,
    )

    return output_path
