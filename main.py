"""Point d'entree en ligne de commande de GeoData Engine."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from core.config import DEFAULT_SETTINGS_PATH, load_settings
from core.workflow import DEFAULT_DATA_DIR, run_pipeline

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "configuration" / "entites_exemple.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GeoData Engine : construit un espace de travail SIG a partir d'une emprise communale."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Fichier CSV des entites a traiter (defaut : data/configuration/entites_exemple.csv)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Racine du dossier data/ (defaut : data/ a la racine du depot)",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help="Fichier de reglages globaux TOML (defaut : data/configuration/settings.toml)",
    )
    parser.add_argument(
        "--buffer-decoupe",
        type=float,
        default=None,
        help="Buffer en metres pour le decoupage des couches (defaut : valeur de settings.toml, sinon 50)",
    )
    parser.add_argument(
        "--buffer-telechargement",
        type=float,
        default=None,
        help=(
            "Buffer en metres pour le calcul automatique de la bbox de telechargement "
            "(defaut : valeur de settings.toml, sinon 250)"
        ),
    )
    parser.add_argument(
        "--include-lidar",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Telecharge aussi les dalles Lidar HD (volumineux). Defaut : valeur de settings.toml.",
    )
    parser.add_argument(
        "--include-ortho",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Telecharge aussi l'orthophotographie 20cm (volumineux). Defaut : valeur de settings.toml.",
    )
    parser.add_argument(
        "--auto-reproject",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Reprojection automatique lors du controle qualite. Defaut : valeur de settings.toml.",
    )
    parser.add_argument(
        "--classify-lidar-from-vectors",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Recale la classification du nuage de points Lidar depuis les couches vecteur "
            "(couteux, cf. processing/lidar/classify.py). Defaut : valeur de settings.toml."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Journalisation detaillee (DEBUG) au lieu du niveau INFO par defaut",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings(args.settings)

    clip_buffer = args.buffer_decoupe if args.buffer_decoupe is not None else settings.buffer_decoupe
    download_buffer = (
        args.buffer_telechargement
        if args.buffer_telechargement is not None
        else settings.buffer_telechargement
    )
    include_lidar = args.include_lidar if args.include_lidar is not None else settings.include_lidar
    include_ortho = args.include_ortho if args.include_ortho is not None else settings.include_ortho
    auto_reproject = (
        args.auto_reproject if args.auto_reproject is not None else settings.auto_reproject
    )
    classify_lidar_from_vectors = (
        args.classify_lidar_from_vectors
        if args.classify_lidar_from_vectors is not None
        else settings.classify_lidar_from_vectors
    )

    geopackage_path, filegdb_path = run_pipeline(
        csv_path=args.csv,
        data_dir=args.data_dir,
        clip_buffer=clip_buffer,
        download_buffer=download_buffer,
        include_lidar=include_lidar,
        include_ortho=include_ortho,
        auto_reproject=auto_reproject,
        classify_lidar_from_vectors=classify_lidar_from_vectors,
    )

    print(f"Projet SIG genere : {geopackage_path} | {filegdb_path}")


if __name__ == "__main__":
    main()
