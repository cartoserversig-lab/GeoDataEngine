"""Classification et filtrage des points (sol, vegetation, bati...)."""

from __future__ import annotations

import logging
from pathlib import Path

from database.metadata import DEFAULT_METADATA_DIR, record_processing
from processing.lidar.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Codes de classification LAS (norme ASPRS, deja utilises par l'IGN dans
# les dalles Lidar HD) appliques par defaut lors du recalage depuis les
# couches vecteur BD TOPO.
DEFAULT_CLASSIFICATION_CODES = {
    "hydro": 9,  # Eau
    "vegetation": 5,  # Vegetation haute (le vecteur ne distingue pas les hauteurs 3/4/5)
    "batiment": 6,  # Bati
}


def classify_from_vectors(
    input_path: str | Path,
    output_path: str | Path,
    layers: dict[str, tuple[str | Path, int]],
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
) -> Path:
    """Recale la classification des points d'apres des couches vecteur (BD TOPO).

    layers associe un nom de theme a (chemin_du_gpkg, code_de_classification
    LAS a appliquer). Pour chaque theme, filters.overlay assigne ce code a
    tout point tombant dans un polygone de la couche correspondante,
    ecrasant la classification IGN existante pour ces points.

    Les themes sont appliques dans l'ordre du dictionnaire : en cas de
    recouvrement entre couches, le dernier theme applique l'emporte (le
    bati doit donc typiquement etre place en dernier).

    Utile notamment pour l'eau (classe 9), rarement identifiee par l'IGN
    dans les dalles Lidar HD alors qu'elle est bien presente dans BD TOPO.

    Chaque chemin de couche vecteur doit etre un GeoPackage mono-couche
    dont le nom de la couche correspond au nom de fichier (convention des
    connecteurs download/*.py de ce projet). Le traitement est trace dans
    les metadonnees (metadata_dir).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = [{"type": "readers.las", "filename": str(input_path)}]
    for theme, (vector_path, code) in layers.items():
        vector_path = Path(vector_path)
        layer_name = vector_path.stem
        stages.append(
            {
                "type": "filters.overlay",
                "dimension": "Classification",
                "datasource": str(vector_path),
                "query": f"SELECT geom, {code} AS classification FROM {layer_name}",
                "column": "classification",
            }
        )
        logger.info("Recalage classification (%s -> code %d) depuis %s", theme, code, vector_path)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    stages.append(
        {
            "type": "writers.las",
            "filename": str(tmp_path),
            "compression": "false",
            "extra_dims": "all",
            "forward": "all",
        }
    )

    _, num_points = run_pipeline(stages)
    tmp_path.replace(output_path)

    record_processing(
        input_path,
        output_path,
        f"classification recalee depuis couches vecteur : {', '.join(layers.keys())}",
        metadata_dir=metadata_dir,
    )

    logger.info("Classification recalee : %d points -> %s", num_points, output_path)
    return output_path
