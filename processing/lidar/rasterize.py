"""Rasterisation du nuage de points (production de MNT/MNS)."""

from __future__ import annotations

import logging
from pathlib import Path

from processing.lidar.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Code de classification LAS du sol, deja assigne par l'IGN dans les dalles Lidar HD.
GROUND_CLASSIFICATION = 2

# Resolution par defaut (metres/pixel) des rasters MNT/MNS produits.
DEFAULT_RESOLUTION = 0.5


def compute_mnt(
    input_path: str | Path,
    output_path: str | Path,
    resolution: float = DEFAULT_RESOLUTION,
    output_type: str = "idw",
) -> Path:
    """Produit le Modele Numerique de Terrain (MNT) a partir des points sol.

    Filtre les points de classification 2 (sol, deja identifies par l'IGN
    dans les dalles Lidar HD), puis les rasterise (writers.gdal) en un
    raster d'altitude sol au format GeoTIFF.

    output_type controle l'interpolation par cellule ('idw' = inverse
    distance weighting, ou 'min'/'max'/'mean'...). Les cellules sans point
    sol a proximite recoivent la valeur NoData (-9999).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        {"type": "readers.las", "filename": str(input_path)},
        {
            "type": "filters.range",
            "limits": f"Classification[{GROUND_CLASSIFICATION}:{GROUND_CLASSIFICATION}]",
        },
        {
            "type": "writers.gdal",
            "filename": str(output_path),
            "resolution": resolution,
            "output_type": output_type,
            "gdaldriver": "GTiff",
            "data_type": "float32",
            "nodata": -9999,
        },
    ]

    _, num_points = run_pipeline(stages)

    logger.info("MNT genere a partir de %d points sol -> %s", num_points, output_path)
    return output_path


def compute_mns(
    input_path: str | Path,
    output_path: str | Path,
    resolution: float = DEFAULT_RESOLUTION,
    output_type: str = "max",
) -> Path:
    """Produit le Modele Numerique de Surface (MNS) a partir de l'ensemble du nuage.

    Contrairement au MNT, aucun filtre de classification n'est applique :
    tous les points (sol, vegetation, bati...) contribuent au raster.
    output_type='max' (par defaut) capte le point le plus haut par cellule,
    donnant le sursol (toits, canopee) plutot que le sol.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        {"type": "readers.las", "filename": str(input_path)},
        {
            "type": "writers.gdal",
            "filename": str(output_path),
            "resolution": resolution,
            "output_type": output_type,
            "gdaldriver": "GTiff",
            "data_type": "float32",
            "nodata": -9999,
        },
    ]

    _, num_points = run_pipeline(stages)

    logger.info("MNS genere a partir de %d points -> %s", num_points, output_path)
    return output_path


def compute_mnh(
    input_path: str | Path,
    output_path: str | Path,
    resolution: float = DEFAULT_RESOLUTION,
    output_type: str = "max",
) -> Path:
    """Produit le Modele Numerique de Hauteur (MNH) a partir du nuage de points.

    filters.hag_nn calcule, pour chaque point, sa hauteur par rapport au
    sol interpole par plus proche voisin parmi les points de classification
    2 (sol). Cette dimension HeightAboveGround est ensuite rasterisee
    (output_type='max' par defaut : hauteur du sursol par cellule -
    canopee, faitage des batiments...), plutot que Z.

    Equivalent, sans avoir a produire ni aligner deux rasters separes, a
    une soustraction MNS - MNT.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        {"type": "readers.las", "filename": str(input_path)},
        {"type": "filters.hag_nn", "class": GROUND_CLASSIFICATION},
        {
            "type": "writers.gdal",
            "filename": str(output_path),
            "resolution": resolution,
            "output_type": output_type,
            "dimension": "HeightAboveGround",
            "gdaldriver": "GTiff",
            "data_type": "float32",
            "nodata": -9999,
        },
    ]

    _, num_points = run_pipeline(stages)

    logger.info("MNH genere a partir de %d points -> %s", num_points, output_path)
    return output_path
