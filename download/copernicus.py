"""Connecteur de telechargement des images Sentinel-2 (Copernicus) via catalogue STAC."""

from __future__ import annotations

import logging
from pathlib import Path

import rioxarray
from pyproj import Transformer
from pystac_client import Client
from rasterio.warp import transform_bounds

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata

logger = logging.getLogger(__name__)

# Catalogue STAC public (Element84 Earth Search) : memes donnees Sentinel-2 que
# le Copernicus Data Space Ecosystem, mais en acces direct sans authentification
# (COG publics sur AWS S3) pour la collection sentinel-2-l2a.
STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Bandes spectrales telechargees par defaut (noms d'assets STAC de la collection).
# La fusion/composite des bandes sera realisee dans une etape de traitement ulterieure.
DEFAULT_BANDS = [
    "coastal",
    "blue",
    "green",
    "red",
    "rededge1",
    "rededge2",
    "rededge3",
    "nir",
    "nir08",
    "nir09",
    "swir16",
    "swir22",
]

MAX_CLOUD_COVER = 20  # % ; seuil sous lequel chercher la scene la plus recente

# Repertoire de sortie par defaut : data/raster/sentinel a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raster" / "sentinel"

_TO_WGS84 = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True)


class CopernicusError(RuntimeError):
    """Erreur lors de la recuperation des images Sentinel-2."""


def _bbox_to_wgs84(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Reprojete une bbox EPSG:2154 en EPSG:4326 (lon/lat), attendu par l'API STAC."""
    xmin, ymin, xmax, ymax = bbox
    lon_min, lat_min = _TO_WGS84.transform(xmin, ymin)
    lon_max, lat_max = _TO_WGS84.transform(xmax, ymax)
    return (lon_min, lat_min, lon_max, lat_max)


def _find_latest_scene(bbox_wgs84: tuple[float, float, float, float], max_cloud_cover: float):
    """Recherche la scene Sentinel-2 la plus recente sous le seuil de nuages donne."""
    catalog = Client.open(STAC_URL)
    search = catalog.search(
        collections=[COLLECTION],
        bbox=bbox_wgs84,
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        sortby=[{"field": "properties.datetime", "direction": "desc"}],
        max_items=1,
    )
    items = list(search.items())
    if not items:
        raise CopernicusError(
            f"Aucune scene Sentinel-2 trouvee sous {max_cloud_cover}% de couverture "
            "nuageuse pour cette emprise. Augmenter max_cloud_cover si besoin."
        )
    return items[0]


def download_sentinel2(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bands: list[str] | None = None,
    max_cloud_cover: float = MAX_CLOUD_COVER,
) -> dict[str, Path]:
    """Telecharge la derniere image Sentinel-2 (toutes bandes) intersectant la bbox (EPSG:2154).

    Interroge le catalogue STAC public d'Element84 (Earth Search) pour la scene
    la plus recente sous le seuil de couverture nuageuse donne, decoupe chaque
    bande sur l'emprise par lecture fenetree du COG distant (pas de telechargement
    de la dalle complete), reprojete en EPSG:2154 et ecrit un GeoTIFF par bande.

    La fusion des bandes est geree dans une etape de traitement ulterieure.

    Retourne un dictionnaire {nom_bande: chemin_du_fichier_tif}.
    """
    bands = bands or DEFAULT_BANDS
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bbox_wgs84 = _bbox_to_wgs84(bbox)
    item = _find_latest_scene(bbox_wgs84, max_cloud_cover)
    logger.info(
        "Scene Sentinel-2 retenue : %s (%s, nuages %.1f%%)",
        item.id,
        item.properties.get("datetime"),
        item.properties.get("eo:cloud_cover", -1),
    )

    written: dict[str, Path] = {}
    for band in bands:
        if band not in item.assets:
            logger.warning("Bande %s absente des assets de la scene %s.", band, item.id)
            continue

        href = item.assets[band].href
        with rioxarray.open_rasterio(href, masked=True) as da:
            raster_crs = da.rio.crs
            bbox_in_raster_crs = transform_bounds(TARGET_CRS, raster_crs, *bbox)

            with da.rio.clip_box(*bbox_in_raster_crs) as clipped:
                with clipped.rio.reproject(TARGET_CRS) as reprojected:
                    output_path = output_dir / f"{item.id}_{band}.tif"
                    reprojected.rio.to_raster(output_path)
                    resolution = abs(float(reprojected.rio.resolution()[0]))

        written[band] = output_path
        logger.info("Bande %s ecrite dans %s", band, output_path)

        record_layer_metadata(
            layer=f"sentinel2_{item.id}_{band}",
            source=f"Sentinel-2 L2A ({item.id})",
            producteur="Copernicus / ESA (via Element84 Earth Search)",
            fichier=output_path,
            crs=TARGET_CRS,
            resolution=resolution,
            traitements=["decoupage sur emprise", "reprojection vers EPSG:2154"],
        )

    return written
