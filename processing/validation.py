"""Controle qualite et validation geometrique des donnees."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pyproj
import rasterio

from core.config import TARGET_CRS

logger = logging.getLogger(__name__)

VECTOR_EXTENSIONS = (".gpkg",)
RASTER_EXTENSIONS = (".tif", ".tiff")
LIDAR_EXTENSIONS = (".laz", ".las")


@dataclass(frozen=True)
class CrsIssue:
    """Signale un fichier dont le CRS ne correspond pas au CRS attendu."""

    fichier: Path
    crs_trouve: str | None
    crs_attendu: str


def _epsg_of(crs) -> str | None:
    if crs is None:
        return None
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs.to_string()


def _vector_crs(path: Path) -> str | None:
    gdf = gpd.read_file(path, rows=1)
    return _epsg_of(gdf.crs)


def _raster_crs(path: Path) -> str | None:
    with rasterio.open(path) as src:
        return _epsg_of(src.crs)


def _lidar_crs(path: Path) -> str | None:
    import pdal

    reader = "readers.copc" if "copc" in path.name.lower() else "readers.las"
    pipeline = pdal.Pipeline(json.dumps([{"type": reader, "filename": str(path)}]))
    pipeline.execute()
    srs_wkt = pipeline.metadata["metadata"][reader]["srs"]["horizontal"]
    return _epsg_of(pyproj.CRS.from_wkt(srs_wkt))


def check_crs_consistency(
    data_dir: str | Path, expected_crs: str = TARGET_CRS
) -> list[CrsIssue]:
    """Verifie que tous les fichiers vecteur/raster/lidar sous data_dir sont dans expected_crs.

    Parcourt recursivement data_dir (.gpkg, .tif/.tiff, .laz/.las). Retourne
    la liste des fichiers dont le CRS differe de expected_crs (liste vide si
    tout est coherent). Les fichiers illisibles sont ignores avec un avertissement
    plutot que de faire echouer le controle.
    """
    data_dir = Path(data_dir)
    issues: list[CrsIssue] = []

    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        try:
            if suffix in VECTOR_EXTENSIONS:
                crs_found = _vector_crs(path)
            elif suffix in RASTER_EXTENSIONS:
                crs_found = _raster_crs(path)
            elif suffix in LIDAR_EXTENSIONS:
                crs_found = _lidar_crs(path)
            else:
                continue
        except Exception as exc:
            logger.warning("Impossible de lire le CRS de %s : %s", path, exc)
            continue

        if crs_found != expected_crs:
            issues.append(CrsIssue(fichier=path, crs_trouve=crs_found, crs_attendu=expected_crs))

    return issues
