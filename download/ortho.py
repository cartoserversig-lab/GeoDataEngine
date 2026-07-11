"""Connecteur de telechargement de l'orthophotographie 20cm (IGN) via WMS."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.merge import merge

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata

logger = logging.getLogger(__name__)

# Verifie manuellement via GetCapabilities le 2026-07-11 :
# https://data.geopf.fr/wms-r/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities
WMS_URL = "https://data.geopf.fr/wms-r/wms"
WMS_VERSION = "1.3.0"
LAYER = "HR.ORTHOIMAGERY.ORTHOPHOTOS"

RESOLUTION = 0.2  # metres par pixel (orthophoto 20 cm)
MAX_TILE_PIXELS = 2048  # taille max (largeur/hauteur) d'une requete WMS unique
REQUEST_TIMEOUT = 120

# Repertoire de sortie par defaut : data/raster/orthophoto a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raster" / "orthophoto"


class OrthoError(RuntimeError):
    """Erreur lors de la recuperation de l'orthophotographie."""


def _tile_grid(
    bbox: tuple[float, float, float, float], resolution: float, max_tile_pixels: int
) -> list[tuple[float, float, float, float]]:
    """Decoupe une bbox en sous-bbox ne depassant pas max_tile_pixels par requete WMS."""
    xmin, ymin, xmax, ymax = bbox
    tile_size = max_tile_pixels * resolution

    n_cols = max(1, math.ceil((xmax - xmin) / tile_size))
    n_rows = max(1, math.ceil((ymax - ymin) / tile_size))

    tiles = []
    for row in range(n_rows):
        for col in range(n_cols):
            tile_xmin = xmin + col * tile_size
            tile_xmax = min(xmin + (col + 1) * tile_size, xmax)
            tile_ymin = ymin + row * tile_size
            tile_ymax = min(ymin + (row + 1) * tile_size, ymax)
            tiles.append((tile_xmin, tile_ymin, tile_xmax, tile_ymax))
    return tiles


def _fetch_tile(bbox: tuple[float, float, float, float], width: int, height: int) -> MemoryFile:
    """Recupere une tuile d'orthophoto via WMS GetMap et la retourne en memoire (GeoTIFF)."""
    xmin, ymin, xmax, ymax = bbox
    params = {
        "SERVICE": "WMS",
        "VERSION": WMS_VERSION,
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "STYLES": "normal",
        "CRS": TARGET_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax}",
        "WIDTH": width,
        "HEIGHT": height,
        "FORMAT": "image/geotiff",
    }
    response = requests.get(WMS_URL, params=params, timeout=REQUEST_TIMEOUT)

    if not response.ok or "image" not in response.headers.get("Content-Type", ""):
        raise OrthoError(
            f"Echec de la requete WMS orthophoto (HTTP {response.status_code}) : {response.text[:300]}"
        )

    return MemoryFile(response.content)


def download_ortho(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    resolution: float = RESOLUTION,
    filename: str = "orthophoto.tif",
) -> Path:
    """Telecharge l'orthophotographie 20cm (IGN) sur la bbox (EPSG:2154) via WMS.

    Decoupe automatiquement l'emprise en tuiles si necessaire (limite de taille
    d'image par requete WMS), puis assemble le resultat en un unique GeoTIFF.

    Retourne le chemin du fichier GeoTIFF ecrit.
    """
    sub_bboxes = _tile_grid(bbox, resolution, MAX_TILE_PIXELS)
    logger.info("Telechargement orthophoto : %d tuile(s) WMS", len(sub_bboxes))

    memfiles: list[MemoryFile] = []
    datasets = []
    try:
        for sub_bbox in sub_bboxes:
            sub_xmin, sub_ymin, sub_xmax, sub_ymax = sub_bbox
            width = max(1, round((sub_xmax - sub_xmin) / resolution))
            height = max(1, round((sub_ymax - sub_ymin) / resolution))

            memfile = _fetch_tile(sub_bbox, width, height)
            memfiles.append(memfile)
            datasets.append(memfile.open())

        mosaic, transform = merge(datasets)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename

        profile = datasets[0].profile
        profile.update(
            driver="GTiff",
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=transform,
            crs=TARGET_CRS,
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(mosaic)
    finally:
        for ds in datasets:
            ds.close()
        for mf in memfiles:
            mf.close()

    logger.info("Orthophoto ecrite dans %s", output_path)

    traitements = [f"assemblage de {len(sub_bboxes)} tuiles WMS"] if len(sub_bboxes) > 1 else []
    record_layer_metadata(
        layer=f"ortho_{output_path.stem}",
        source="Orthophotographie 20cm (IGN)",
        producteur="IGN",
        fichier=output_path,
        crs=TARGET_CRS,
        resolution=resolution,
        traitements=traitements,
    )

    return output_path
