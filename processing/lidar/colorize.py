"""Colorisation du nuage de points a partir d'un raster (orthophotographie)."""

from __future__ import annotations

import logging
from pathlib import Path

from database.metadata import DEFAULT_METADATA_DIR, record_processing
from processing.lidar.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Association par defaut bandes orthophoto IGN (RVB) -> dimensions LAS.
DEFAULT_DIMENSIONS = {"Red": 1, "Green": 2, "Blue": 3}

# Format de point LAS 1.4 incluant GPS time + RGB (compatible avec les
# dimensions deja presentes dans les dalles Lidar HD IGN).
RGB_POINT_FORMAT = 7


def colorize_from_raster(
    input_path: str | Path,
    raster_path: str | Path,
    output_path: str | Path | None = None,
    dimensions: dict[str, int] | None = None,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Assigne Red/Green/Blue a chaque point depuis un raster (orthophoto).

    raster_path est attendu dans le meme CRS que le nuage de points
    (EPSG:2154 par convention du projet). filters.colorization lit la
    valeur du raster sous chaque point (X, Y) et l'assigne aux dimensions
    indiquees par dimensions (par defaut, bandes 1/2/3 de l'orthophoto RVB
    IGN -> Red/Green/Blue).

    Le format de point LAS source (Lidar HD IGN, format 6) ne supporte pas
    les dimensions Red/Green/Blue : l'ecriture force donc le format 7 (LAS
    1.4, GPS time + RGB), quel que soit le format d'entree.

    Ecrase le fichier d'origine par defaut (output_path non fourni). Le
    traitement est trace dans les metadonnees (metadata_dir).
    """
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path
    raster_path = Path(raster_path)
    dimensions = dimensions or DEFAULT_DIMENSIONS

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        {"type": "readers.las", "filename": str(input_path)},
        {
            "type": "filters.colorization",
            "raster": str(raster_path),
            "dimensions": ",".join(f"{dim}:{band}" for dim, band in dimensions.items()),
        },
        {
            "type": "writers.las",
            "filename": str(tmp_path),
            "compression": "false",
            "extra_dims": "all",
            "forward": "all",
            "format": RGB_POINT_FORMAT,
        },
    ]

    _, num_points = run_pipeline(stages)
    tmp_path.replace(output_path)

    record_processing(
        input_path, output_path, f"colorisation RVB depuis {raster_path.name}",
        metadata_dir=metadata_dir,
    )

    logger.info("Nuage de points colorise : %d points -> %s", num_points, output_path)
    return output_path
