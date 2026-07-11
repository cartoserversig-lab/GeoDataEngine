"""Connecteur de telechargement des zones reglementees/protegees (PatriNat/OFB) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from core.config import TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import WfsError, fetch_wfs_features

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"

# Repertoire de sortie par defaut : data/raw/vector/zones_protegees a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "vector" / "zones_protegees"

# Couches de zones reglementees/protegees interrogees par defaut (typenames
# WFS IGN Geoplateforme, source PatriNat/OFB - distinctes de BD TOPO).
# A verifier/ajuster si une couche renvoie 0 entite, via GetCapabilities :
# https://data.geopf.fr/wfs/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities
DEFAULT_LAYERS = {
    "znieff1": "patrinat_znieff1:znieff1",
    "znieff2": "patrinat_znieff2:znieff2",
    "aire_protection_habitats_naturels": "patrinat_aphn:aire_protection_habitats_naturels",
    "reserve_biologique": "patrinat_rb:reserve_biologique",
    "patrimoine_mondial_unesco": "patrinat_bpm:Bien_patrimoine_mondial_UNESCO",
    "perimetre_site_fragile": "PROTECTEDAREAS.PRSF:prsf",
}


class ZonesProtegeesError(WfsError):
    """Erreur lors de l'interrogation des couches de zones reglementees/protegees."""


def download_zones_protegees(
    bbox: tuple[float, float, float, float],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    layers: dict[str, str] | None = None,
) -> dict[str, Path]:
    """Telecharge les zones reglementees/protegees intersectant la bbox (EPSG:2154).

    Ecrit chaque couche en GeoPackage. Retourne un dictionnaire
    {nom_couche: chemin_du_fichier_gpkg} pour les couches ayant renvoye au
    moins une entite.
    """
    layers = layers or DEFAULT_LAYERS
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for name, typename in layers.items():
        logger.info("Telechargement zones protegees : %s", name)
        try:
            gdf: gpd.GeoDataFrame = fetch_wfs_features(WFS_URL, typename, bbox, TARGET_CRS)
        except WfsError as exc:
            raise ZonesProtegeesError(str(exc)) from exc

        if gdf.empty:
            logger.warning("Aucune entite recuperee pour la couche %s sur cette emprise.", name)
            continue

        output_path = output_dir / f"{name}.gpkg"
        gdf.to_file(output_path, driver="GPKG")
        written[name] = output_path
        logger.info("%s : %d entites ecrites dans %s", name, len(gdf), output_path)

        record_layer_metadata(
            layer=f"zones_protegees_{name}",
            source="PatriNat / OFB",
            producteur="Museum national d'Histoire naturelle (MNHN) / OFB",
            fichier=output_path,
            crs=TARGET_CRS,
        )

    return written
