"""Connecteur de telechargement de la BD TOPO (IGN) via le service WFS de la Geoplateforme."""

from __future__ import annotations

import datetime
import io
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from core.config import TARGET_CRS

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"
WFS_VERSION = "2.0.0"
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60

# Repertoire de sortie par defaut : data/vector/bd_topo a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "vector" / "bd_topo"

# Couches BD TOPO interrogees par defaut (typenames WFS IGN Geoplateforme).
# A verifier/ajuster si une couche renvoie 0 entite, via GetCapabilities :
# https://data.geopf.fr/wfs/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities
DEFAULT_LAYERS = {
    "batiment": "BDTOPO_V3:batiment",
    "troncon_de_route": "BDTOPO_V3:troncon_de_route",
    "troncon_hydrographique": "BDTOPO_V3:troncon_hydrographique",
}


class BdTopoError(RuntimeError):
    """Erreur lors de l'interrogation du service WFS BD TOPO."""


def _fetch_layer(typename: str, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Recupere l'integralite d'une couche WFS BD TOPO sur l'emprise donnee (pagination incluse)."""
    xmin, ymin, xmax, ymax = bbox
    bbox_param = f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}"

    frames: list[gpd.GeoDataFrame] = []
    start_index = 0

    while True:
        params = {
            "SERVICE": "WFS",
            "VERSION": WFS_VERSION,
            "REQUEST": "GetFeature",
            "TYPENAMES": typename,
            "SRSNAME": TARGET_CRS,
            "BBOX": bbox_param,
            "OUTPUTFORMAT": "application/json",
            "COUNT": PAGE_SIZE,
            "STARTINDEX": start_index,
        }
        response = requests.get(WFS_URL, params=params, timeout=REQUEST_TIMEOUT)

        if not response.ok:
            raise BdTopoError(
                f"Echec de la requete WFS pour {typename} (HTTP {response.status_code}) : "
                f"{response.text[:300]}"
            )

        if "ExceptionReport" in response.text[:500]:
            raise BdTopoError(f"Erreur renvoyee par le WFS pour {typename} : {response.text[:500]}")

        page = gpd.read_file(io.BytesIO(response.content))
        if page.empty:
            break

        frames.append(page)
        if len(page) < PAGE_SIZE:
            break
        start_index += PAGE_SIZE

    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=TARGET_CRS)
    return _normalize_datetime_columns(result)


def _normalize_datetime_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convertit les colonnes date/heure en chaines ISO.

    Contournement d'un bug pyogrio a l'ecriture GPKG des colonnes datetime64[ms]
    (resolution non nanoseconde introduite par pandas 2.x).
    """
    geometry_col = gdf.geometry.name
    for col in gdf.columns:
        if col == geometry_col:
            continue

        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif gdf[col].dtype == object:
            gdf[col] = gdf[col].apply(
                lambda v: v.isoformat() if isinstance(v, (pd.Timestamp, datetime.date)) else v
            )
    return gdf


def download_bd_topo(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    layers: dict[str, str] | None = None,
) -> dict[str, Path]:
    """Telecharge les couches BD TOPO intersectant la bbox (EPSG:2154) et les ecrit en GeoPackage.

    Retourne un dictionnaire {nom_couche: chemin_du_fichier_gpkg} pour les couches
    ayant renvoye au moins une entite.
    """
    layers = layers or DEFAULT_LAYERS
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for name, typename in layers.items():
        logger.info("Telechargement BD TOPO : %s", name)
        gdf = _fetch_layer(typename, bbox)

        if gdf.empty:
            logger.warning("Aucune entite recuperee pour la couche %s sur cette emprise.", name)
            continue

        output_path = output_dir / f"{name}.gpkg"
        gdf.to_file(output_path, driver="GPKG")
        written[name] = output_path
        logger.info("%s : %d entites ecrites dans %s", name, len(gdf), output_path)

    return written
