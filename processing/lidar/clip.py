"""Decoupage du nuage de points selon l'emprise du projet."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from processing.lidar.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def clip_las_to_boundary(
    input_path: str | Path,
    boundary: gpd.GeoDataFrame,
    buffer_distance: float = 0,
    output_path: str | Path | None = None,
) -> Path:
    """Decoupe un nuage de points LAS/LAZ selon une limite (avec buffer optionnel).

    boundary est attendue dans le meme CRS que le nuage de points (EPSG:2154
    par convention du projet). Comme pour le vecteur (processing.clipping),
    buffer_distance (en metres) permet de conserver les points au-dela de la
    limite stricte de la commune. Le decoupage utilise filters.crop avec le
    WKT de la geometrie (dissoute) de boundary + buffer.

    Ecrase le fichier d'origine par defaut (output_path non fourni).
    """
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path

    clip_geometry = boundary.geometry
    if buffer_distance:
        clip_geometry = clip_geometry.buffer(buffer_distance)
    polygon_wkt = clip_geometry.union_all().wkt

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        {"type": "readers.las", "filename": str(input_path)},
        {"type": "filters.crop", "polygon": polygon_wkt},
        {
            "type": "writers.las",
            "filename": str(tmp_path),
            "compression": "false",
            "extra_dims": "all",
            "forward": "all",
        },
    ]

    _, num_points = run_pipeline(stages)
    tmp_path.replace(output_path)

    logger.info("Nuage de points decoupe : %d points -> %s", num_points, output_path)
    return output_path
