"""Creation et alimentation de la base de donnees geographique (GeoPackage)."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)


def compile_geopackage(
    processed_vector_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Compile toutes les couches vectorielles traitees en un GeoPackage multi-couches.

    Parcourt processed_vector_dir recursivement (data/processed/vector/<theme>/<couche>.gpkg)
    et ecrit chaque couche non vide dans output_path, nommee "<theme>_<couche>"
    (sans repeter le theme si le nom de la couche le contient deja) pour eviter
    toute collision entre themes.

    Ecrase output_path s'il existe deja.
    """
    processed_vector_dir = Path(processed_vector_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    layer_count = 0
    for path in sorted(processed_vector_dir.rglob("*.gpkg")):
        relative = path.relative_to(processed_vector_dir)
        theme = relative.parts[0]
        layer_name = path.stem if path.stem.startswith(theme) else f"{theme}_{path.stem}"

        gdf = gpd.read_file(path)
        if gdf.empty:
            logger.warning("Couche vide ignoree : %s", relative)
            continue

        gdf.to_file(output_path, layer=layer_name, driver="GPKG")
        layer_count += 1
        logger.info("Couche compilee : %s (%d entites)", layer_name, len(gdf))

    logger.info("%d couches compilees dans %s", layer_count, output_path)
    return output_path
