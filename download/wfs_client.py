"""Client generique pour interroger un service WFS (GetFeature pagine par bbox)."""

from __future__ import annotations

import datetime
import io

import geopandas as gpd
import pandas as pd
import requests

DEFAULT_PAGE_SIZE = 1000
DEFAULT_TIMEOUT = 60
DEFAULT_VERSION = "2.0.0"


class WfsError(RuntimeError):
    """Erreur lors de l'interrogation d'un service WFS."""


def fetch_wfs_features(
    wfs_url: str,
    typename: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    version: str = DEFAULT_VERSION,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
) -> gpd.GeoDataFrame:
    """Recupere l'integralite d'une couche WFS sur l'emprise donnee (pagination incluse)."""
    xmin, ymin, xmax, ymax = bbox
    bbox_param = f"{xmin},{ymin},{xmax},{ymax},{crs}"

    frames: list[gpd.GeoDataFrame] = []
    start_index = 0

    while True:
        params = {
            "SERVICE": "WFS",
            "VERSION": version,
            "REQUEST": "GetFeature",
            "TYPENAMES": typename,
            "SRSNAME": crs,
            "BBOX": bbox_param,
            "OUTPUTFORMAT": "application/json",
            "COUNT": page_size,
            "STARTINDEX": start_index,
        }
        response = requests.get(wfs_url, params=params, timeout=timeout)

        if not response.ok:
            raise WfsError(
                f"Echec de la requete WFS pour {typename} (HTTP {response.status_code}) : "
                f"{response.text[:300]}"
            )

        if "ExceptionReport" in response.text[:500]:
            raise WfsError(f"Erreur renvoyee par le WFS pour {typename} : {response.text[:500]}")

        page = gpd.read_file(io.BytesIO(response.content))
        if page.empty:
            break

        frames.append(page)
        if len(page) < page_size:
            break
        start_index += page_size

    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=crs)

    result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs)
    return normalize_datetime_columns(result)


def normalize_datetime_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convertit les colonnes date/heure en chaines ISO.

    Contournement d'un bug pyogrio a l'ecriture GPKG des colonnes datetime64[ms]
    (resolution non nanoseconde introduite par pandas 2.x) et des colonnes
    datetime timezone-aware.
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
