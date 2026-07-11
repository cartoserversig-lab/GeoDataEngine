"""Chargement et validation de la configuration du projet."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# CRS unique pour toutes les données traitées par le moteur (V1).
TARGET_CRS = "EPSG:2154"

REQUIRED_COLUMNS = ("nom_entite", "type_entite", "code_insee")


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
