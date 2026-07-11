"""Connecteur de telechargement des reseaux techniques (BD TOPO, IGN) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import WfsError, fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"

# Repertoire de sortie par defaut : data/raw/vector/reseaux a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "vector" / "reseaux"

# Couches de reseaux techniques interrogees par defaut (typenames WFS IGN Geoplateforme).
# A verifier/ajuster si une couche renvoie 0 entite, via GetCapabilities :
# https://data.geopf.fr/wfs/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities
DEFAULT_LAYERS = {
    "ligne_electrique": "BDTOPO_V3:ligne_electrique",
    "poste_de_transformation": "BDTOPO_V3:poste_de_transformation",
    "pylone": "BDTOPO_V3:pylone",
    "canalisation": "BDTOPO_V3:canalisation",
    "reservoir": "BDTOPO_V3:reservoir",
    "point_du_reseau": "BDTOPO_V3:point_du_reseau",
}


class ReseauxError(WfsError):
    """Erreur lors de l'interrogation des couches de reseaux techniques."""


def download_reseaux(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    layers: dict[str, str] | None = None,
) -> dict[str, Path]:
    """Telecharge les couches de reseaux techniques intersectant la bbox (EPSG:2154).

    Ecrit chaque couche en GeoPackage. Retourne un dictionnaire
    {nom_couche: chemin_du_fichier_gpkg} pour les couches ayant renvoye au
    moins une entite.
    """
    layers = layers or DEFAULT_LAYERS
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for name, typename in layers.items():
        logger.info("Telechargement reseaux : %s", name)
        try:
            gdf: gpd.GeoDataFrame = fetch_wfs_features(WFS_URL, typename, bbox, TARGET_CRS)
        except WfsError as exc:
            raise ReseauxError(str(exc)) from exc

        if gdf.empty:
            logger.warning("Aucune entite recuperee pour la couche %s sur cette emprise.", name)
            continue

        output_path = output_dir / f"{name}.gpkg"
        gdf.to_file(output_path, driver="GPKG")
        written[name] = output_path
        logger.info("%s : %d entites ecrites dans %s", name, len(gdf), output_path)

        record_layer_metadata(
            layer=f"reseaux_{name}",
            source="BD TOPO (IGN)",
            producteur="IGN",
            fichier=output_path,
            crs=TARGET_CRS,
        )

    return written
