"""Connecteur de telechargement des infrastructures OpenStreetMap (ecoles, commerces, sante...)."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from pyproj import Transformer

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import normalize_datetime_columns

logger = logging.getLogger(__name__)

# Repertoire de sortie par defaut : data/raw/vector/infrastructures a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "vector" / "infrastructures"

# Categories d'infrastructures interrogees par defaut (tags OpenStreetMap).
# Reference des tags : https://wiki.openstreetmap.org/wiki/Map_features
DEFAULT_LAYERS = {
    "ecoles": {"amenity": ["school", "kindergarten", "college", "university"]},
    "restauration": {"amenity": ["restaurant", "fast_food", "cafe", "bar", "pub"]},
    "commerces": {"shop": True},
    "sante": {"amenity": ["hospital", "clinic", "pharmacy", "doctors"]},
    "services_publics": {"amenity": ["townhall", "post_office", "police", "fire_station"]},
    "sport_loisirs": {"leisure": True},
}

_TO_WGS84 = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True)


class OsmError(RuntimeError):
    """Erreur lors de l'interrogation d'OpenStreetMap."""


def _bbox_to_wgs84(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Reprojete une bbox EPSG:2154 en EPSG:4326 (lon/lat), attendu par osmnx/Overpass."""
    xmin, ymin, xmax, ymax = bbox
    lon_min, lat_min = _TO_WGS84.transform(xmin, ymin)
    lon_max, lat_max = _TO_WGS84.transform(xmax, ymax)
    return (lon_min, lat_min, lon_max, lat_max)


def _sanitize_for_gpkg(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Aplatit l'index et convertit les colonnes non primitives (listes, dicts) en chaines.

    Necessaire car osmnx renvoie un (Multi)Index (element_type, osmid) et des
    colonnes dont certaines valeurs sont des listes (tags OSM multi-valeurs),
    non supportees telles quelles par l'ecriture GPKG.
    """
    gdf = gdf.reset_index(drop=False)
    geometry_col = gdf.geometry.name
    for col in gdf.columns:
        if col == geometry_col:
            continue
        if gdf[col].dtype == object:
            gdf[col] = gdf[col].apply(
                lambda v: str(v) if isinstance(v, (list, dict, set, tuple)) else v
            )
    return normalize_datetime_columns(gdf)


def download_osm_infrastructures(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    layers: dict[str, dict] | None = None,
) -> dict[str, Path]:
    """Telecharge les infrastructures OSM intersectant la bbox (EPSG:2154) et les ecrit en GeoPackage.

    La bbox est fournie en EPSG:2154 (convention du projet) ; elle est reprojetee
    en EPSG:4326 pour interroger OpenStreetMap (Overpass API via osmnx), puis
    chaque couche est reprojetee en EPSG:2154 avant ecriture.

    Retourne un dictionnaire {nom_couche: chemin_du_fichier_gpkg} pour les
    couches ayant renvoye au moins une entite.
    """
    layers = layers or DEFAULT_LAYERS
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bbox_wgs84 = _bbox_to_wgs84(bbox)

    written: dict[str, Path] = {}
    for name, tags in layers.items():
        logger.info("Telechargement OSM : %s", name)
        try:
            gdf = ox.features_from_bbox(bbox_wgs84, tags)
        except Exception as exc:
            logger.warning("Aucune entite recuperee pour la couche %s (%s).", name, exc)
            continue

        if gdf.empty:
            logger.warning("Aucune entite recuperee pour la couche %s sur cette emprise.", name)
            continue

        gdf = gdf.to_crs(TARGET_CRS)
        gdf = _sanitize_for_gpkg(gdf)

        output_path = output_dir / f"{name}.gpkg"
        gdf.to_file(output_path, driver="GPKG")
        written[name] = output_path
        logger.info("%s : %d entites ecrites dans %s", name, len(gdf), output_path)

        record_layer_metadata(
            layer=f"osm_{name}",
            source="OpenStreetMap",
            producteur="OpenStreetMap contributors",
            fichier=output_path,
            crs=TARGET_CRS,
            traitements=["reprojection EPSG:4326 -> EPSG:2154"],
        )

    return written
