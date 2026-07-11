"""Decoupage des donnees selon l'emprise du projet."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask as rasterio_mask

logger = logging.getLogger(__name__)


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


def clip_all_vector_layers(
    raw_dir: str | Path,
    processed_dir: str | Path,
    boundary: gpd.GeoDataFrame,
    buffer_distance: float = 0,
) -> dict[str, Path]:
    """Decoupe tous les GeoPackage sous raw_dir selon une limite (+ buffer optionnel).

    Parcourt raw_dir recursivement (chaque theme telecharge par les
    connecteurs : bd_topo/, infrastructures/, adresses/, cadastre/,
    reseaux/, limites_administratives/) et ecrit chaque couche decoupee
    dans processed_dir en preservant la meme arborescence thematique.

    Les couches dont le decoupage ne renvoie aucune entite, ou qui ne
    peuvent pas etre lues, sont ignorees (avertissement) plutot que de
    faire echouer l'ensemble.

    Retourne un dictionnaire {chemin_relatif: chemin_ecrit}.
    """
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)

    written: dict[str, Path] = {}
    for path in sorted(raw_dir.rglob("*.gpkg")):
        relative = path.relative_to(raw_dir)

        try:
            clipped = clip_to_boundary(path, boundary, buffer_distance=buffer_distance)
        except Exception as exc:
            logger.warning("Echec du decoupage de %s : %s", relative, exc)
            continue

        if clipped.empty:
            logger.warning("Decoupage vide pour %s, fichier non ecrit.", relative)
            continue

        output_path = processed_dir / relative
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clipped.to_file(output_path, driver="GPKG")
        written[str(relative)] = output_path
        logger.info("%s : %d entites decoupees -> %s", relative, len(clipped), output_path)

    return written


def clip_raster_to_boundary(
    input_path: str | Path,
    boundary: gpd.GeoDataFrame,
    buffer_distance: float = 0,
    output_path: str | Path | None = None,
) -> Path:
    """Masque un raster selon une limite (avec buffer optionnel).

    Contrairement au vecteur, le raster reste rectangulaire : les pixels
    hors du polygone (boundary + buffer) sont mis a NoData, et le raster
    est recadre au rectangle englobant minimal de ce polygone.

    Ecrase le fichier d'origine par defaut (output_path non fourni).
    """
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path

    clip_geometry = boundary
    if buffer_distance:
        clip_geometry = boundary.assign(geometry=boundary.geometry.buffer(buffer_distance))

    with rasterio.open(input_path) as src:
        nodata = src.nodata if src.nodata is not None else 0
        out_image, out_transform = rasterio_mask(
            src, clip_geometry.geometry, crop=True, nodata=nodata
        )
        profile = src.profile.copy()

    profile.update(
        height=out_image.shape[1],
        width=out_image.shape[2],
        transform=out_transform,
        nodata=nodata,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with rasterio.open(tmp_path, "w", **profile) as dst:
        dst.write(out_image)
    tmp_path.replace(output_path)

    logger.info("Raster masque selon la limite : %s", output_path)
    return output_path
