"""Controle qualite et validation geometrique des donnees."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pyproj
import rasterio
from shapely.validation import explain_validity

from core.config import TARGET_CRS

logger = logging.getLogger(__name__)

VECTOR_EXTENSIONS = (".gpkg",)
RASTER_EXTENSIONS = (".tif", ".tiff")
LIDAR_EXTENSIONS = (".laz", ".las")


@dataclass(frozen=True)
class CrsIssue:
    """Signale un fichier (ou une couche) dont le CRS ne correspond pas au CRS attendu."""

    fichier: Path
    couche: str | None
    crs_trouve: str | None
    crs_attendu: str


def _epsg_of(crs) -> str | None:
    if crs is None:
        return None
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs.to_string()


def _vector_layer_crs(path: Path, layer: str | None) -> str | None:
    gdf = gpd.read_file(path, layer=layer, rows=1)
    return _epsg_of(gdf.crs)


def _raster_crs(path: Path) -> str | None:
    with rasterio.open(path) as src:
        return _epsg_of(src.crs)


def _lidar_crs(path: Path) -> str | None:
    import pdal

    reader = "readers.copc" if "copc" in path.name.lower() else "readers.las"
    pipeline = pdal.Pipeline(json.dumps([{"type": reader, "filename": str(path)}]))
    pipeline.execute()
    srs_wkt = pipeline.metadata["metadata"][reader]["srs"]["horizontal"]
    return _epsg_of(pyproj.CRS.from_wkt(srs_wkt))


def check_crs_consistency(
    data_dir: str | Path, expected_crs: str = TARGET_CRS
) -> list[CrsIssue]:
    """Verifie que tous les fichiers vecteur/raster/lidar sous data_dir sont dans expected_crs.

    Parcourt recursivement data_dir (.gpkg, .tif/.tiff, .laz/.las). Un
    GeoPackage multi-couches (ex : projet.gpkg) est verifie couche par
    couche. Retourne la liste des fichiers/couches dont le CRS differe de
    expected_crs (liste vide si tout est coherent). Les fichiers illisibles
    sont ignores avec un avertissement plutot que de faire echouer le controle.
    """
    import fiona

    data_dir = Path(data_dir)
    issues: list[CrsIssue] = []

    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        if suffix in VECTOR_EXTENSIONS:
            try:
                layers = fiona.listlayers(path)
            except Exception as exc:
                logger.warning("Impossible de lister les couches de %s : %s", path, exc)
                continue

            for layer in layers:
                try:
                    crs_found = _vector_layer_crs(path, layer)
                except Exception as exc:
                    logger.warning(
                        "Impossible de lire le CRS de %s::%s : %s", path, layer, exc
                    )
                    continue

                if crs_found != expected_crs:
                    issues.append(
                        CrsIssue(
                            fichier=path,
                            couche=layer if len(layers) > 1 else None,
                            crs_trouve=crs_found,
                            crs_attendu=expected_crs,
                        )
                    )
            continue

        try:
            if suffix in RASTER_EXTENSIONS:
                crs_found = _raster_crs(path)
            elif suffix in LIDAR_EXTENSIONS:
                crs_found = _lidar_crs(path)
            else:
                continue
        except Exception as exc:
            logger.warning("Impossible de lire le CRS de %s : %s", path, exc)
            continue

        if crs_found != expected_crs:
            issues.append(
                CrsIssue(fichier=path, couche=None, crs_trouve=crs_found, crs_attendu=expected_crs)
            )

    return issues


# Emprise approximative de la France metropolitaine en Lambert-93 (EPSG:2154),
# utilisee comme controle de coherence spatiale (detection de coordonnees
# aberrantes). N'inclut pas les DOM-TOM, hors perimetre initial du projet.
FRANCE_METROPOLITAINE_BOUNDS = (0.0, 6_000_000.0, 1_300_000.0, 7_200_000.0)


@dataclass(frozen=True)
class GeometryIssue:
    """Signale un probleme detecte sur une entite d'une couche vectorielle."""

    fichier: Path
    couche: str | None
    index: int
    probleme: str


def check_vector_layer(
    path: str | Path,
    layer: str | None = None,
    sane_bounds: tuple[float, float, float, float] | None = FRANCE_METROPOLITAINE_BOUNDS,
) -> list[GeometryIssue]:
    """Controles automatiques d'une couche vectorielle (CDC section 5.1).

    Verifie : systeme de coordonnees identifie, presence d'une geometrie
    valide (non absente/vide), absence d'erreur geometrique (auto-
    intersection...), et coherence spatiale (coordonnees dans une emprise
    plausible, par defaut la France metropolitaine).

    layer permet de cibler une couche precise dans un GeoPackage
    multi-couches (ex : projet.gpkg) ; laisser a None pour un fichier a
    couche unique.
    """
    path = Path(path)
    gdf = gpd.read_file(path, layer=layer)
    issues: list[GeometryIssue] = []

    if gdf.crs is None:
        issues.append(
            GeometryIssue(
                fichier=path, couche=layer, index=-1, probleme="Systeme de coordonnees non identifie"
            )
        )

    geometry = gdf.geometry
    empty_mask = geometry.isna() | geometry.is_empty
    for idx in gdf.index[empty_mask]:
        issues.append(
            GeometryIssue(fichier=path, couche=layer, index=idx, probleme="Geometrie absente ou vide")
        )

    valid_mask = geometry.is_valid
    invalid_idx = gdf.index[~valid_mask & ~empty_mask]
    for idx in invalid_idx:
        detail = explain_validity(geometry[idx])
        issues.append(
            GeometryIssue(
                fichier=path, couche=layer, index=idx, probleme=f"Geometrie invalide : {detail}"
            )
        )

    if sane_bounds is not None:
        bxmin, bymin, bxmax, bymax = sane_bounds
        bounds = geometry.bounds
        out_of_bounds_mask = (
            (bounds["minx"] < bxmin)
            | (bounds["maxx"] > bxmax)
            | (bounds["miny"] < bymin)
            | (bounds["maxy"] > bymax)
        )
        for idx in gdf.index[out_of_bounds_mask & ~empty_mask]:
            issues.append(
                GeometryIssue(
                    fichier=path,
                    couche=layer,
                    index=idx,
                    probleme="Coordonnees hors de l'emprise attendue",
                )
            )

    return issues


def check_all_vector_layers(
    data_dir: str | Path,
    sane_bounds: tuple[float, float, float, float] | None = FRANCE_METROPOLITAINE_BOUNDS,
) -> dict[str, list[GeometryIssue]]:
    """Applique check_vector_layer a toutes les couches de tous les GeoPackage sous data_dir.

    Chaque fichier .gpkg est ouvert avec fiona pour en lister les couches
    (un GeoPackage peut en contenir plusieurs, ex : projet.gpkg), et chacune
    est validee individuellement.

    Retourne un dictionnaire {cle: liste_des_problemes}, ne contenant que
    les couches ayant au moins un probleme detecte. La cle est le chemin
    relatif du fichier, suffixe de "::<couche>" si le fichier contient
    plusieurs couches.
    """
    import fiona

    data_dir = Path(data_dir)
    results: dict[str, list[GeometryIssue]] = {}

    for path in sorted(data_dir.rglob("*.gpkg")):
        relative = str(path.relative_to(data_dir))

        try:
            layers = fiona.listlayers(path)
        except Exception as exc:
            logger.warning("Impossible de lister les couches de %s : %s", relative, exc)
            results[relative] = [
                GeometryIssue(fichier=path, couche=None, index=-1, probleme=f"Fichier illisible : {exc}")
            ]
            continue

        for layer in layers:
            key = relative if len(layers) == 1 else f"{relative}::{layer}"
            try:
                issues = check_vector_layer(path, layer=layer, sane_bounds=sane_bounds)
            except Exception as exc:
                logger.warning("Impossible de valider %s : %s", key, exc)
                issues = [
                    GeometryIssue(
                        fichier=path, couche=layer, index=-1, probleme=f"Couche illisible : {exc}"
                    )
                ]

            if issues:
                results[key] = issues

    return results


def format_quality_report(
    crs_issues: list[CrsIssue],
    geometry_issues: dict[str, list[GeometryIssue]],
) -> str:
    """Formate un rapport texte lisible du controle qualite (CRS + geometrie, CDC section 5.1)."""
    lines = [
        "=== Controle qualite GeoData Engine ===",
        f"Date : {datetime.now().isoformat(timespec='seconds')}",
        "",
        "--- Coherence des systemes de coordonnees (CRS) ---",
    ]

    if crs_issues:
        for issue in crs_issues:
            label = str(issue.fichier) + (f"::{issue.couche}" if issue.couche else "")
            lines.append(f"  - {label} : {issue.crs_trouve} (attendu {issue.crs_attendu})")
    else:
        lines.append("OK : aucune incoherence detectee.")

    lines.append("")
    lines.append("--- Controles geometriques (CRS identifie, geometrie valide, coherence spatiale) ---")

    if geometry_issues:
        for key, issues in geometry_issues.items():
            for issue in issues:
                lines.append(f"  - {key} : {issue.probleme}")
    else:
        lines.append("OK : aucun probleme detecte.")

    return "\n".join(lines) + "\n"


def write_quality_report(
    crs_issues: list[CrsIssue],
    geometry_issues: dict[str, list[GeometryIssue]],
    output_path: str | Path,
) -> Path:
    """Ecrit le rapport de controle qualite (voir format_quality_report) dans un fichier texte."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_quality_report(crs_issues, geometry_issues), encoding="utf-8")
    return output_path
