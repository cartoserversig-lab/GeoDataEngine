"""Connecteur de telechargement de la BD TOPO (IGN) via le service WFS de la Geoplateforme."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import WfsError, fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"

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
    # Occupation du sol
    "haie": "BDTOPO_V3:haie",
    "zone_de_vegetation": "BDTOPO_V3:zone_de_vegetation",
    "foret_publique": "BDTOPO_V3:foret_publique",
    "zone_d_habitation": "BDTOPO_V3:zone_d_habitation",
    "cimetiere": "BDTOPO_V3:cimetiere",
    "parc_ou_reserve": "BDTOPO_V3:parc_ou_reserve",
    "zone_d_activite_ou_d_interet": "BDTOPO_V3:zone_d_activite_ou_d_interet",
    "terrain_de_sport": "BDTOPO_V3:terrain_de_sport",
}


class BdTopoError(WfsError):
    """Erreur lors de l'interrogation du service WFS BD TOPO."""


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
        try:
            gdf: gpd.GeoDataFrame = fetch_wfs_features(WFS_URL, typename, bbox, TARGET_CRS)
        except WfsError as exc:
            raise BdTopoError(str(exc)) from exc

        if gdf.empty:
            logger.warning("Aucune entite recuperee pour la couche %s sur cette emprise.", name)
            continue

        output_path = output_dir / f"{name}.gpkg"
        gdf.to_file(output_path, driver="GPKG")
        written[name] = output_path
        logger.info("%s : %d entites ecrites dans %s", name, len(gdf), output_path)

        record_layer_metadata(
            layer=f"bd_topo_{name}",
            source="BD TOPO (IGN)",
            producteur="IGN",
            fichier=output_path,
            crs=TARGET_CRS,
        )

    return written
