"""Fusion de plusieurs dalles ou nuages de points."""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import TARGET_CRS
from database.metadata import DEFAULT_METADATA_DIR, record_layer_metadata
from processing.lidar.pipeline import LidarProcessingError, run_pipeline

logger = logging.getLogger(__name__)

# Nom de fichier par defaut pour le nuage de points fusionne (avant decoupage),
# conserve a cote des dalles source dans data/raw/raster/lidar/.
DEFAULT_MERGED_FILENAME = "nuage_points.las"


def merge_laz_tiles(
    input_dir: str | Path,
    output_path: str | Path,
    pattern: str = "*.laz",
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Decompresse et fusionne les dalles LAZ d'un repertoire en un seul fichier LAS.

    Chaque dalle (y compris au format COPC, une variante LAZ) est lue par
    readers.las, qui gere nativement la decompression LASzip : aucune etape
    de decompression separee n'est necessaire. filters.merge combine
    l'ensemble des points en un seul nuage, ecrit non compresse
    (writers.las, compression=False) dans output_path.

    Le traitement est trace dans les metadonnees (metadata_dir). Comme la
    fusion combine plusieurs dalles source, l'enregistrement est cree
    directement (source="Lidar HD (IGN)") plutot que d'heriter d'un
    enregistrement source unique (cf. database.metadata.record_processing,
    pense pour un traitement 1 entree -> 1 sortie).

    Leve LidarProcessingError si aucune dalle ne correspond au motif, ou si
    la fusion PDAL echoue.
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    tiles = sorted(input_dir.glob(pattern))
    if not tiles:
        raise LidarProcessingError(
            f"Aucune dalle LAZ trouvee dans {input_dir} (motif '{pattern}')."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Fusion de %d dalle(s) LAZ en un seul fichier LAS...", len(tiles))

    stages = [{"type": "readers.las", "filename": str(tile)} for tile in tiles]
    stages.append({"type": "filters.merge"})
    stages.append(
        {
            "type": "writers.las",
            "filename": str(output_path),
            "compression": "false",
            "extra_dims": "all",
            "forward": "all",
        }
    )

    _, num_points = run_pipeline(stages)

    record_layer_metadata(
        layer=output_path.stem,
        source="Lidar HD (IGN)",
        producteur="IGN",
        fichier=output_path,
        crs=TARGET_CRS,
        traitements=[f"decompression et fusion de {len(tiles)} dalle(s) LAZ"],
        metadata_dir=metadata_dir,
    )

    logger.info("Fusion terminee : %d points ecrits dans %s", num_points, output_path)
    return output_path
