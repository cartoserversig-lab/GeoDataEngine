"""Controle des systemes de coordonnees et reprojection automatique."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

from core.config import TARGET_CRS
from database.metadata import DEFAULT_METADATA_DIR, record_processing

logger = logging.getLogger(__name__)

VECTOR_EXTENSIONS = (".gpkg",)
RASTER_EXTENSIONS = (".tif", ".tiff")


class ReprojectionError(RuntimeError):
    """Erreur lors de la reprojection d'un fichier."""


def reproject_vector(
    path: str | Path,
    target_crs: str = TARGET_CRS,
    output_path: str | Path | None = None,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Reprojete un fichier vecteur (GeoPackage) vers target_crs.

    Ecrase le fichier d'origine par defaut (output_path non fourni). Le
    traitement est trace dans les metadonnees (metadata_dir, cf.
    database.metadata.record_processing).
    """
    path = Path(path)
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(target_crs)

    output_path = Path(output_path) if output_path else path
    gdf.to_file(output_path, driver="GPKG")
    record_processing(path, output_path, f"reprojection vers {target_crs}", metadata_dir=metadata_dir)
    logger.info("Fichier vecteur reprojete vers %s : %s", target_crs, output_path)
    return output_path


def reproject_raster(
    path: str | Path,
    target_crs: str = TARGET_CRS,
    output_path: str | Path | None = None,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Reprojete un fichier raster (GeoTIFF) vers target_crs.

    Ecrase le fichier d'origine par defaut (output_path non fourni). Passe
    par un fichier temporaire pour eviter de lire/ecrire la source en meme
    temps. Le traitement est trace dans les metadonnees (metadata_dir, cf.
    database.metadata.record_processing).
    """
    path = Path(path)
    output_path = Path(output_path) if output_path else path
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    with rasterio.open(path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=target_crs, transform=transform, width=width, height=height)

        with rasterio.open(tmp_path, "w", **profile) as dst:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

    tmp_path.replace(output_path)
    record_processing(path, output_path, f"reprojection vers {target_crs}", metadata_dir=metadata_dir)
    logger.info("Fichier raster reprojete vers %s : %s", target_crs, output_path)
    return output_path


def reproject_to_target_crs(
    path: str | Path,
    target_crs: str = TARGET_CRS,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Reprojete un fichier vecteur ou raster vers target_crs, en place, selon son extension."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in VECTOR_EXTENSIONS:
        return reproject_vector(path, target_crs, metadata_dir=metadata_dir)
    if suffix in RASTER_EXTENSIONS:
        return reproject_raster(path, target_crs, metadata_dir=metadata_dir)

    raise ReprojectionError(f"Type de fichier non pris en charge pour la reprojection : {path}")
