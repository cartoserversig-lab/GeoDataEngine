"""Decoupage des donnees selon l'emprise du projet."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd


def clip_to_boundary(
    input_path: str | Path,
    boundary: gpd.GeoDataFrame,
    buffer_distance: float = 0,
    output_path: str | Path | None = None,
) -> gpd.GeoDataFrame:
    """Decoupe une couche vectorielle selon une limite (avec buffer optionnel).

    boundary est attendue dans le meme CRS que la couche a decouper (EPSG:2154
    par convention du projet). buffer_distance (en metres) permet de conserver
    une legere continuite des donnees autour de la limite plutot qu'une coupe
    nette (ex : batiments a cheval sur la frontiere communale).

    Si output_path est fourni, le resultat decoupe est egalement ecrit en
    GeoPackage a cet emplacement.
    """
    gdf = gpd.read_file(input_path)

    clip_geometry = boundary
    if buffer_distance:
        clip_geometry = boundary.assign(geometry=boundary.geometry.buffer(buffer_distance))

    clipped = gpd.clip(gdf, clip_geometry)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clipped.to_file(output_path, driver="GPKG")

    return clipped
