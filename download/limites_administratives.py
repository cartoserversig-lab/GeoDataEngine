"""Connecteur de recuperation des limites administratives (IGN ADMIN EXPRESS) via WFS."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd

from core.config import DEFAULT_BUFFER_TELECHARGEMENT, TARGET_CRS
from database.metadata import record_layer_metadata
from download.wfs_client import fetch_wfs_features

if TYPE_CHECKING:
    from core.config import Entity

logger = logging.getLogger(__name__)

WFS_URL = "https://data.geopf.fr/wfs/wfs"
COMMUNE_TYPENAME = "ADMINEXPRESS-COG.LATEST:commune"
CODE_INSEE_FIELD = "code_insee"

# Marge (en metres) ajoutee autour de la limite communale lorsque la bbox
# de telechargement doit etre calculee automatiquement (voir resolve_bbox).
# Reference core.config pour rester coherent avec settings.toml.
DEFAULT_BUFFER = DEFAULT_BUFFER_TELECHARGEMENT

# Repertoire de sortie par defaut : data/raw/vector/limites_administratives a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "vector" / "limites_administratives"


class LimitesAdministrativesError(RuntimeError):
    """Erreur lors de la recuperation des limites administratives."""


def fetch_commune_boundary(
    code_insee: str, bbox: tuple[float, float, float, float] | None = None
) -> gpd.GeoDataFrame:
    """Recupere la limite officielle (ADMIN EXPRESS IGN) de la commune correspondant a code_insee.

    Si bbox est fournie, elle restreint la requete WFS (doit contenir la
    commune) et le resultat est filtre sur le code INSEE exact, car la bbox
    peut intersecter des communes voisines. Si bbox est omise, la recherche
    se fait directement par code INSEE (CQL_FILTER), sans emprise prealable.
    """
    if bbox is not None:
        communes = fetch_wfs_features(WFS_URL, COMMUNE_TYPENAME, bbox, TARGET_CRS)
        match = communes[communes[CODE_INSEE_FIELD] == code_insee]
    else:
        cql_filter = f"{CODE_INSEE_FIELD}='{code_insee}'"
        match = fetch_wfs_features(WFS_URL, COMMUNE_TYPENAME, None, TARGET_CRS, cql_filter=cql_filter)

    if match.empty:
        raise LimitesAdministrativesError(
            f"Aucune commune trouvee pour le code INSEE {code_insee!r}."
        )

    return match.reset_index(drop=True)


def resolve_bbox(
    entity: "Entity",
    buffer_distance: float = DEFAULT_BUFFER,
) -> tuple[float, float, float, float]:
    """Determine la bbox de telechargement (EPSG:2154) d'une entite.

    Si l'entite fournit deja une bbox (colonne renseignee dans le CSV), elle
    est utilisee telle quelle (cas d'un perimetre d'etude personnalise). Sinon,
    la bbox est calculee a partir de la limite communale officielle (ADMIN
    EXPRESS IGN) etendue d'un buffer, pour garder du contexte autour de la
    commune (utile notamment pour l'imagerie) plutot qu'une coupure trop stricte.
    """
    if entity.bbox is not None:
        return entity.bbox

    boundary = fetch_commune_boundary(entity.code_insee)
    xmin, ymin, xmax, ymax = boundary.total_bounds
    return (
        xmin - buffer_distance,
        ymin - buffer_distance,
        xmax + buffer_distance,
        ymax + buffer_distance,
    )


def download_commune_boundary(
    code_insee: str,
    bbox: tuple[float, float, float, float] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    filename: str | None = None,
) -> Path:
    """Recupere la limite communale et l'ecrit en GeoPackage.

    Retourne le chemin du fichier GeoPackage ecrit.
    """
    boundary = fetch_commune_boundary(code_insee, bbox)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (filename or f"commune_{code_insee}.gpkg")
    boundary.to_file(output_path, driver="GPKG")
    logger.info("Limite communale de %s ecrite dans %s", code_insee, output_path)

    record_layer_metadata(
        layer=f"limite_communale_{code_insee}",
        source="ADMIN EXPRESS (IGN)",
        producteur="IGN",
        fichier=output_path,
        crs=TARGET_CRS,
    )

    return output_path
