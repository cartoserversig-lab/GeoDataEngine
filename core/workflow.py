"""Orchestration de la chaine de traitement (acquisition, harmonisation, organisation)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import geopandas as gpd

from core.config import Entity, load_entities
from database.filegdb import compile_filegdb
from database.geopackage import compile_geopackage
from download.ban import download_ban
from download.bd_topo import download_bd_topo
from download.cadastre import download_cadastre
from download.limites_administratives import (
    download_commune_boundary,
    fetch_commune_boundary,
    resolve_bbox,
)
from download.lidar import download_lidar
from download.ortho import download_ortho
from download.osm import download_osm_infrastructures
from download.reseaux import download_reseaux
from download.risques import download_risques
from download.zones_protegees import download_zones_protegees
from processing.clipping import clip_all_vector_layers, clip_raster_to_boundary
from processing.lidar.classify import classify_from_vectors
from processing.lidar.clip import clip_las_to_boundary
from processing.lidar.colorize import colorize_from_raster
from processing.lidar.merge import merge_laz_tiles
from processing.lidar.rasterize import compute_mnh, compute_mns, compute_mnt
from processing.reprojection import ReprojectionError, reproject_to_target_crs
from processing.validation import check_all_vector_layers, check_crs_consistency, write_quality_report

logger = logging.getLogger(__name__)

# Themes vecteur (deja decoupes) et code de classification LAS a appliquer,
# utilises par process_lidar lorsque classify_from_vectors_enabled est actif.
# Cf. processing.lidar.classify.DEFAULT_CLASSIFICATION_CODES.
LIDAR_CLASSIFICATION_LAYERS = {
    "hydro": (Path("bd_topo") / "surface_hydrographique.gpkg", 9),
    "vegetation": (Path("bd_topo") / "zone_de_vegetation.gpkg", 5),
    "batiment": (Path("bd_topo") / "batiment.gpkg", 6),
}

# Repertoire de donnees par defaut : data/ a la racine du depot.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Buffer par defaut (en metres) applique lors du decoupage des couches
# autour de la limite communale (distinct du buffer de resolve_bbox, qui
# determine l'emprise de telechargement).
DEFAULT_CLIP_BUFFER = 50


def run_quality_checks(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    auto_reproject: bool = False,
    write_log: bool = True,
) -> None:
    """Etape "Controle qualite" du pipeline (CDC section 5.1), puis "Reprojection".

    Verifie que chaque fichier vecteur, raster ou lidar sous data_dir est
    dans le CRS attendu du projet (core.config.TARGET_CRS), et que chaque
    couche vectorielle a un systeme de coordonnees identifie, des
    geometries valides et non vides, et des coordonnees dans une emprise
    plausible (coherence spatiale).

    Si auto_reproject est True, les fichiers vecteur/raster non conformes
    au CRS attendu sont automatiquement reprojetes (etape "Reprojection"
    du CDC), puis le controle CRS est relance. Le lidar (.laz/.las) n'est
    pas reprojete automatiquement.

    Si write_log est True (defaut), un rapport texte est ecrit dans
    data_dir/logs/controle_qualite_<horodatage>.txt, que des problemes
    aient ete detectes ou non.

    Une erreur est levee si des incoherences de CRS ou des problemes
    geometriques subsistent apres l'eventuelle reprojection automatique :
    ces derniers ne peuvent pas etre corriges automatiquement.
    """
    data_dir = Path(data_dir)
    crs_issues = check_crs_consistency(data_dir)

    if crs_issues and auto_reproject:
        for issue in crs_issues:
            if issue.couche is not None:
                # Fichier multi-couches (ex : projet.gpkg, base compilee) : la
                # reprojection en place ecraserait les autres couches, on ne
                # la tente pas automatiquement.
                logger.warning(
                    "Reprojection automatique ignoree pour %s::%s (fichier multi-couches).",
                    issue.fichier,
                    issue.couche,
                )
                continue
            try:
                reproject_to_target_crs(issue.fichier)
            except ReprojectionError:
                logger.warning("Reprojection non prise en charge pour %s.", issue.fichier)

        crs_issues = check_crs_consistency(data_dir)

    geometry_issues = check_all_vector_layers(data_dir)

    if write_log:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = data_dir / "logs" / f"controle_qualite_{timestamp}.txt"
        write_quality_report(crs_issues, geometry_issues, log_path)
        logger.info("Rapport de controle qualite ecrit dans %s", log_path)

    if crs_issues:
        details = "\n".join(
            f"  - {issue.fichier}"
            + (f"::{issue.couche}" if issue.couche else "")
            + f" : {issue.crs_trouve} (attendu {issue.crs_attendu})"
            for issue in crs_issues
        )
        raise ValueError(f"Incoherence de CRS detectee :\n{details}")

    if geometry_issues:
        details = "\n".join(
            f"  - {key} : {issue.probleme}"
            for key, issues in geometry_issues.items()
            for issue in issues
        )
        raise ValueError(f"Problemes geometriques detectes :\n{details}")

    logger.info("Controle qualite : OK, aucune incoherence CRS ni geometrique detectee.")


def download_all_layers(
    entity: Entity,
    bbox: tuple[float, float, float, float],
    include_lidar: bool = False,
    include_ortho: bool = False,
) -> None:
    """Etape "Telechargement automatique" du pipeline : lance tous les connecteurs.

    Le Lidar HD et l'orthophotographie representent potentiellement
    plusieurs dizaines de dalles/tuiles (voir les notebooks 03 et 04) :
    ils ne sont telecharges que si include_lidar/include_ortho sont
    explicitement actives.
    """
    logger.info("Telechargement BD TOPO...")
    download_bd_topo(bbox)

    logger.info("Telechargement infrastructures OSM...")
    download_osm_infrastructures(bbox)

    logger.info("Telechargement cadastre...")
    download_cadastre(entity.code_insee, bbox)

    logger.info("Telechargement reseaux techniques...")
    download_reseaux(bbox)

    logger.info("Telechargement adresses (BAN)...")
    download_ban(entity.code_insee, bbox)

    logger.info("Telechargement limite communale...")
    download_commune_boundary(entity.code_insee)

    logger.info("Recuperation des risques...")
    download_risques(entity.code_insee)

    logger.info("Telechargement zones reglementees/protegees...")
    download_zones_protegees(bbox)

    if include_lidar:
        logger.info("Telechargement Lidar HD...")
        download_lidar(bbox)

    if include_ortho:
        logger.info("Telechargement orthophotographie...")
        download_ortho(bbox)


def process_lidar(
    data_dir: Path,
    boundary: gpd.GeoDataFrame,
    clip_buffer: float = DEFAULT_CLIP_BUFFER,
    include_ortho: bool = False,
    classify_from_vectors_enabled: bool = False,
) -> Path | None:
    """Etape de traitement Lidar (CDC : decompression, decoupage, harmonisation).

    Fusionne, decoupe et rasterise (MNT/MNS/MNH) le nuage de points Lidar
    HD brut ; colorise depuis l'orthophoto si include_ortho est actif et
    que l'orthophoto traitee est disponible. Ne modifie jamais les dalles
    source (data/raw/raster/lidar/) : tous les produits traites sont
    ecrits dans data/processed/raster/lidar/.

    La classification depuis les couches vecteur (filters.overlay,
    processing.lidar.classify) est couteuse - voir notebook 20, un test
    sur un nuage complet non decoupe a ete interrompu apres 20+ minutes -
    et n'est executee que si classify_from_vectors_enabled est actif.
    Utilise les couches vecteur deja decoupees (data/processed/vector/),
    donc doit etre appelee apres clip_all_vector_layers.

    Retourne le chemin du nuage de points final traite, ou None si aucune
    dalle Lidar HD n'a ete telechargee.
    """
    raw_lidar_dir = data_dir / "raw" / "raster" / "lidar"
    processed_lidar_dir = data_dir / "processed" / "raster" / "lidar"

    if not any(raw_lidar_dir.glob("*.laz")):
        logger.info("Aucune dalle Lidar HD dans %s, traitement Lidar ignore.", raw_lidar_dir)
        return None

    las_path = processed_lidar_dir / "nuage_points.las"

    logger.info("Fusion des dalles Lidar HD...")
    merge_laz_tiles(raw_lidar_dir, las_path)

    logger.info("Decoupage du nuage de points...")
    clip_las_to_boundary(las_path, boundary, buffer_distance=clip_buffer, output_path=las_path)

    if include_ortho:
        ortho_path = data_dir / "processed" / "raster" / "orthophoto.tif"
        if ortho_path.exists():
            logger.info("Colorisation du nuage de points depuis l'orthophoto...")
            colorize_from_raster(las_path, ortho_path, output_path=las_path)
        else:
            logger.warning("Orthophoto traitee introuvable (%s), colorisation ignoree.", ortho_path)

    logger.info("Rasterisation MNT/MNS/MNH...")
    compute_mnt(las_path, processed_lidar_dir / "mnt.tif")
    compute_mns(las_path, processed_lidar_dir / "mns.tif")
    compute_mnh(las_path, processed_lidar_dir / "mnh.tif")

    if classify_from_vectors_enabled:
        processed_vector_dir = data_dir / "processed" / "vector"
        layers = {
            theme: (processed_vector_dir / relative, code)
            for theme, (relative, code) in LIDAR_CLASSIFICATION_LAYERS.items()
            if (processed_vector_dir / relative).exists()
        }
        if layers:
            logger.info("Classification du nuage de points depuis les couches vecteur...")
            classify_from_vectors(las_path, las_path, layers)
        else:
            logger.warning("Aucune couche vecteur disponible, classification Lidar ignoree.")

    return las_path


def run_pipeline(
    csv_path: str | Path,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    clip_buffer: float = DEFAULT_CLIP_BUFFER,
    download_buffer: float | None = None,
    include_lidar: bool = False,
    include_ortho: bool = False,
    auto_reproject: bool = True,
    classify_lidar_from_vectors: bool = False,
) -> tuple[Path, Path]:
    """Execute la chaine de traitement complete (CDC section 5.3) pour chaque entite du CSV.

    Emprise utilisateur -> Identification des donnees necessaires ->
    Telechargement automatique -> Controle qualite -> Reprojection ->
    Decoupage -> Organisation -> Creation GeoDatabase -> Projet SIG final.

    download_buffer (metres) determine l'emprise de telechargement lorsque
    la bbox doit etre calculee automatiquement (voir resolve_bbox) ; laisser
    a None pour utiliser sa valeur par defaut. clip_buffer (metres) est
    utilise separement lors du decoupage des couches.

    Retourne (chemin_geopackage, chemin_filegdb), les deux bases de
    donnees geographiques compilees dans data/processed/database/.
    """
    data_dir = Path(data_dir)
    processed_vector_dir = data_dir / "processed" / "vector"
    processed_raster_dir = data_dir / "processed" / "raster"
    geopackage_path = data_dir / "processed" / "database" / "projet.gpkg"
    filegdb_path = data_dir / "processed" / "database" / "projet.gdb"

    entities = load_entities(csv_path)
    logger.info("%d entite(s) a traiter.", len(entities))

    for entity in entities:
        logger.info("=== Traitement de %s (%s) ===", entity.nom, entity.code_insee)

        bbox = (
            resolve_bbox(entity)
            if download_buffer is None
            else resolve_bbox(entity, buffer_distance=download_buffer)
        )

        download_all_layers(entity, bbox, include_lidar=include_lidar, include_ortho=include_ortho)

        run_quality_checks(data_dir, auto_reproject=auto_reproject)

        boundary = fetch_commune_boundary(entity.code_insee)

        clip_all_vector_layers(
            data_dir / "raw" / "vector", processed_vector_dir, boundary, buffer_distance=clip_buffer
        )

        if include_ortho:
            ortho_path = data_dir / "raw" / "raster" / "orthophoto" / "orthophoto.tif"
            if ortho_path.exists():
                processed_raster_dir.mkdir(parents=True, exist_ok=True)
                clip_raster_to_boundary(
                    ortho_path,
                    boundary,
                    buffer_distance=clip_buffer,
                    output_path=processed_raster_dir / "orthophoto.tif",
                )

        if include_lidar:
            process_lidar(
                data_dir,
                boundary,
                clip_buffer=clip_buffer,
                include_ortho=include_ortho,
                classify_from_vectors_enabled=classify_lidar_from_vectors,
            )

    compile_geopackage(processed_vector_dir, geopackage_path)
    compile_filegdb(processed_vector_dir, filegdb_path)

    logger.info(
        "Pipeline termine. GeoPackage : %s | File Geodatabase : %s",
        geopackage_path,
        filegdb_path,
    )
    return geopackage_path, filegdb_path
