"""Creation et alimentation de la base de donnees geographique (File Geodatabase ArcGIS)."""

from __future__ import annotations

import logging
import os
import shutil
import stat
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)

# Une feature class File Geodatabase n'accepte qu'un seul type de geometrie,
# contrairement a une couche GeoPackage qui peut melanger Point/Polygon (ex :
# les couches infrastructures issues d'OSM). Ces familles regroupent les
# variantes simples et multi- d'un meme type pour eviter une explosion du
# nombre de sous-couches.
_GEOMETRY_FAMILIES = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "ligne",
    "MultiLineString": "ligne",
    "Polygon": "polygone",
    "MultiPolygon": "polygone",
}

# Options de creation de couche : preserve les entiers 64 bits (sinon
# ecrits en Float64 par defaut, avec perte de precision).
_LAYER_CREATION_OPTIONS = {"TARGET_ARCGIS_VERSION": "ARCGIS_PRO_3_2_OR_LATER"}


class FileGdbError(RuntimeError):
    """Erreur lors de la compilation de la File Geodatabase finale."""


def _clear_readonly_and_retry(func, path, exc_info) -> None:
    """onerror de shutil.rmtree : leve le drapeau lecture-seule puis reessaie.

    OneDrive (Files On-Demand) marque frequemment lecture-seule les
    dossiers qu'il vient de synchroniser, y compris juste apres la
    creation d'un .gdb par un run precedent : shutil.rmtree echoue alors
    avec PermissionError des le premier fichier rencontre, meme si aucun
    programme externe n'a reellement le dossier ouvert.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _write_layer(gdf: gpd.GeoDataFrame, output_path: Path, layer_name: str) -> None:
    gdf.to_file(
        output_path,
        layer=layer_name,
        driver="OpenFileGDB",
        layer_options=_LAYER_CREATION_OPTIONS,
    )


def compile_filegdb(
    processed_vector_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Compile toutes les couches vectorielles traitees en une File Geodatabase ArcGIS (.gdb).

    Parcourt processed_vector_dir recursivement (data/processed/vector/<theme>/<couche>.gpkg)
    et ecrit chaque couche non vide dans output_path (pilote GDAL OpenFileGDB,
    lecture/ecriture native, aucune dependance ESRI requise), nommee
    "<theme>_<couche>" comme pour le GeoPackage (database/geopackage.py).

    Si une couche source melange plusieurs types de geometrie (point et
    polygone par exemple, frequent sur les couches infrastructures issues
    d'OSM), elle est eclatee en plusieurs feature classes, une par famille
    de geometrie ("<couche>_point", "<couche>_ligne", "<couche>_polygone"),
    puisqu'une feature class File Geodatabase n'accepte qu'un seul type.

    Une File Geodatabase est un dossier (extension .gdb) et non un fichier
    unique : output_path est supprime et recree s'il existe deja.
    """
    processed_vector_dir = Path(processed_vector_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        try:
            shutil.rmtree(output_path, onerror=_clear_readonly_and_retry)
        except PermissionError as exc:
            raise FileGdbError(
                f"Impossible de remplacer {output_path} : le dossier est ouvert dans un autre "
                "programme (ArcGIS Pro, explorateur de fichiers...). Fermez-le puis reessayez."
            ) from exc

    layer_count = 0
    for path in sorted(processed_vector_dir.rglob("*.gpkg")):
        relative = path.relative_to(processed_vector_dir)
        theme = relative.parts[0]
        layer_name = path.stem if path.stem.startswith(theme) else f"{theme}_{path.stem}"

        gdf = gpd.read_file(path)
        if gdf.empty:
            logger.warning("Couche vide ignoree : %s", relative)
            continue

        families = gdf.geometry.geom_type.map(lambda t: _GEOMETRY_FAMILIES.get(t, t))

        if families.nunique() == 1:
            _write_layer(gdf, output_path, layer_name)
            layer_count += 1
            logger.info("Couche compilee : %s (%d entites)", layer_name, len(gdf))
            continue

        for family in sorted(families.unique()):
            sub_gdf = gdf[families == family]
            sub_layer_name = f"{layer_name}_{family}"
            _write_layer(sub_gdf, output_path, sub_layer_name)
            layer_count += 1
            logger.info(
                "Couche compilee : %s (%d entites, sous-ensemble %s de %s)",
                sub_layer_name,
                len(sub_gdf),
                family,
                relative,
            )

    logger.info("%d couches compilees dans %s", layer_count, output_path)
    return output_path
