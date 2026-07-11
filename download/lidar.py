"""Connecteur de telechargement des dalles Lidar HD (IGN) au format LAZ."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from core.config import TARGET_CRS
from download.wfs_client import WfsError, fetch_wfs_features

logger = logging.getLogger(__name__)

# Index des dalles (tableau d'assemblage) Lidar HD, interroge par bbox.
# Verifie manuellement via GetCapabilities le 2026-07-11 :
# https://data.geopf.fr/wfs/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities
TILE_INDEX_WFS_URL = "https://data.geopf.fr/wfs/wfs"
TILE_INDEX_TYPENAME = "IGNF_NUAGES-DE-POINTS-LIDAR-HD:dalle"

# Colonnes de l'index portant l'URL de telechargement et le nom de fichier local.
TILE_URL_FIELD = "url"
TILE_FILENAME_FIELD = "name_download"

DOWNLOAD_TIMEOUT = 300
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

# Repertoire de sortie par defaut : data/lidar a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "lidar"


class LidarError(RuntimeError):
    """Erreur lors de la recuperation des dalles Lidar HD."""


def _download_tile(url: str, output_path: Path) -> None:
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
        if not response.ok:
            raise LidarError(f"Echec du telechargement de la dalle {url} (HTTP {response.status_code}).")

        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                f.write(chunk)


def download_lidar(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Telecharge les dalles Lidar HD (.laz) intersectant la bbox (EPSG:2154).

    Interroge l'index des dalles (tableau d'assemblage) sur la bbox, puis
    telecharge chaque fichier LAZ intersectant via l'URL fournie par l'index.
    Les dalles deja presentes dans output_dir ne sont pas re-telechargees.

    Retourne la liste des chemins des fichiers LAZ disponibles.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        tiles = fetch_wfs_features(TILE_INDEX_WFS_URL, TILE_INDEX_TYPENAME, bbox, TARGET_CRS)
    except WfsError as exc:
        raise LidarError(f"Echec de la recuperation de l'index des dalles Lidar HD : {exc}") from exc

    if tiles.empty:
        logger.warning("Aucune dalle Lidar HD trouvee pour cette emprise.")
        return []

    missing = [f for f in (TILE_URL_FIELD, TILE_FILENAME_FIELD) if f not in tiles.columns]
    if missing:
        raise LidarError(
            f"Colonne(s) {missing} absente(s) de l'index des dalles "
            f"(colonnes disponibles : {list(tiles.columns)}). "
            "Verifier TILE_INDEX_TYPENAME / TILE_URL_FIELD / TILE_FILENAME_FIELD dans download/lidar.py."
        )

    downloaded: list[Path] = []
    for _, tile in tiles.iterrows():
        url = tile[TILE_URL_FIELD]
        filename = tile[TILE_FILENAME_FIELD]
        output_path = output_dir / filename

        if output_path.exists():
            logger.info("Dalle deja presente, telechargement ignore : %s", filename)
            downloaded.append(output_path)
            continue

        logger.info("Telechargement de la dalle Lidar HD : %s", filename)
        _download_tile(url, output_path)
        downloaded.append(output_path)

    return downloaded
