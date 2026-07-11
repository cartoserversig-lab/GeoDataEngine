"""Chargement et validation de la configuration du projet."""

from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass
from pathlib import Path

# CRS unique pour toutes les données traitées par le moteur (V1). Choix
# architectural fixe : ni configurable ni modifiable via settings.toml,
# car tout le pipeline (validation, reprojection...) le suppose partout.
TARGET_CRS = "EPSG:2154"

REQUIRED_COLUMNS = ("nom_entite", "type_entite", "code_insee")

# Repertoire de configuration par defaut : data/configuration a la racine du depot.
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "data" / "configuration"
DEFAULT_SETTINGS_PATH = DEFAULT_CONFIG_DIR / "settings.toml"

# Valeurs par defaut des reglages globaux (utilisees si settings.toml est absent
# ou ne precise pas une cle donnee).
DEFAULT_BUFFER_DECOUPE = 50.0
DEFAULT_BUFFER_TELECHARGEMENT = 250.0


class ConfigError(ValueError):
    """Erreur de lecture ou de validation du fichier d'entités."""


@dataclass(frozen=True)
class Entity:
    """Entité géographique (commune, EPCI, syndicat...) à traiter par le moteur."""

    nom: str
    type_entite: str
    code_insee: str
    # (xmin, ymin, xmax, ymax) en EPSG:2154, ou None si a calculer depuis la
    # limite communale officielle (voir download.limites_administratives.resolve_bbox).
    bbox: tuple[float, float, float, float] | None = None


def _parse_bbox(raw: str, row_number: int) -> tuple[float, float, float, float]:
    cleaned = raw.strip().strip("[]")
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) != 4:
        raise ConfigError(
            f"Ligne {row_number} : bbox invalide ({raw!r}), "
            "4 valeurs attendues au format [xmin,ymin,xmax,ymax]."
        )

    try:
        xmin, ymin, xmax, ymax = (float(p) for p in parts)
    except ValueError as exc:
        raise ConfigError(f"Ligne {row_number} : bbox non numérique ({raw!r}).") from exc

    if xmin >= xmax or ymin >= ymax:
        raise ConfigError(
            f"Ligne {row_number} : bbox incohérente ({raw!r}), "
            "xmin doit être < xmax et ymin doit être < ymax."
        )

    return (xmin, ymin, xmax, ymax)


def load_entities(csv_path: str | Path, delimiter: str = ";") -> list[Entity]:
    """Charge et valide le CSV des entités à traiter.

    Colonnes attendues : nom_entite, type_entite, code_insee, et
    optionnellement bbox (format [xmin,ymin,xmax,ymax] en EPSG:2154). Si la
    colonne bbox est absente ou vide pour une ligne, elle sera calculée plus
    tard depuis la limite communale officielle (voir
    download.limites_administratives.resolve_bbox).
    Le délimiteur par défaut est ";" pour éviter tout conflit avec les
    virgules internes à la bbox.
    """
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise ConfigError(f"Fichier introuvable : {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        missing = [col for col in REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise ConfigError(
                f"Colonnes manquantes dans {csv_path.name} : {', '.join(missing)}"
            )

        entities: list[Entity] = []
        for row_number, row in enumerate(reader, start=2):  # ligne 1 = en-tête
            nom = (row["nom_entite"] or "").strip()
            type_entite = (row["type_entite"] or "").strip()
            code_insee = (row["code_insee"] or "").strip()

            if not nom:
                raise ConfigError(f"Ligne {row_number} : nom_entite manquant.")
            if not code_insee:
                raise ConfigError(f"Ligne {row_number} : code_insee manquant.")

            bbox_raw = (row.get("bbox") or "").strip()
            bbox = _parse_bbox(bbox_raw, row_number) if bbox_raw else None
            entities.append(
                Entity(nom=nom, type_entite=type_entite, code_insee=code_insee, bbox=bbox)
            )

    if not entities:
        raise ConfigError(f"Aucune entité trouvée dans {csv_path.name}.")

    return entities


@dataclass(frozen=True)
class Settings:
    """Réglages globaux du pipeline (data/configuration/settings.toml).

    Ne contient que des paramètres d'exécution (buffers, options de
    téléchargement...). Le CRS cible n'en fait pas partie : voir TARGET_CRS.
    """

    buffer_decoupe: float = DEFAULT_BUFFER_DECOUPE
    buffer_telechargement: float = DEFAULT_BUFFER_TELECHARGEMENT
    include_lidar: bool = False
    include_ortho: bool = False
    auto_reproject: bool = True
    # Desactive par defaut : filters.overlay (classification depuis les
    # couches vecteur) est couteux et peut prendre des heures sur un nuage
    # de points a l'echelle d'une commune entiere (voir notebook 20).
    classify_lidar_from_vectors: bool = False


def load_settings(path: str | Path = DEFAULT_SETTINGS_PATH) -> Settings:
    """Charge les réglages globaux du pipeline depuis un fichier TOML.

    Si le fichier est absent, retourne les valeurs par défaut (Settings()).
    Toute clé absente du fichier utilise egalement sa valeur par défaut.
    """
    path = Path(path)
    if not path.is_file():
        return Settings()

    with path.open("rb") as f:
        data = tomllib.load(f)

    return Settings(
        buffer_decoupe=data.get("buffer_decoupe", DEFAULT_BUFFER_DECOUPE),
        buffer_telechargement=data.get("buffer_telechargement", DEFAULT_BUFFER_TELECHARGEMENT),
        include_lidar=data.get("include_lidar", False),
        include_ortho=data.get("include_ortho", False),
        auto_reproject=data.get("auto_reproject", True),
        classify_lidar_from_vectors=data.get("classify_lidar_from_vectors", False),
    )
