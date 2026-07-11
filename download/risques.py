"""Connecteur de recuperation des risques naturels et technologiques (API Georisques)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from database.metadata import record_layer_metadata

logger = logging.getLogger(__name__)

API_URL = "https://georisques.gouv.fr/api/v1"
REQUEST_TIMEOUT = 30

# Repertoire de sortie par defaut : data/raw/risques a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "risques"


class RisquesError(RuntimeError):
    """Erreur lors de l'interrogation de l'API Georisques."""


def _get(endpoint: str, code_insee: str) -> dict:
    url = f"{API_URL}/{endpoint}"
    response = requests.get(url, params={"code_insee": code_insee}, timeout=REQUEST_TIMEOUT)

    if not response.ok:
        raise RisquesError(
            f"Echec de la requete Georisques {endpoint} (HTTP {response.status_code})."
        )

    data = response.json().get("data") or []
    return data[0] if data else {}


def fetch_risques(code_insee: str) -> dict:
    """Recupere les risques naturels/technologiques et donnees d'alea d'une commune.

    Interroge l'API publique Georisques (donnees attributaires par commune,
    pas de geometrie) : liste des risques applicables (GASPAR), zone de
    sismicite reglementaire, potentiel radon.
    """
    risques = _get("gaspar/risques", code_insee)
    sismique = _get("zonage_sismique", code_insee)
    radon = _get("radon", code_insee)

    return {
        "code_insee": code_insee,
        "risques_gaspar": [
            {"num_risque": r["num_risque"], "libelle": r["libelle_risque_long"]}
            for r in risques.get("risques_detail", [])
        ],
        "zone_sismicite": sismique.get("zone_sismicite"),
        "code_zone_sismicite": sismique.get("code_zone"),
        "classe_potentiel_radon": radon.get("classe_potentiel"),
    }


def download_risques(
    code_insee: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    filename: str | None = None,
) -> Path:
    """Recupere les risques d'une commune et les ecrit en JSON.

    Retourne le chemin du fichier JSON ecrit.
    """
    risques = fetch_risques(code_insee)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (filename or f"risques_{code_insee}.json")
    output_path.write_text(json.dumps(risques, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Risques de la commune %s ecrits dans %s", code_insee, output_path)

    record_layer_metadata(
        layer=f"risques_{code_insee}",
        source="Georisques (API)",
        producteur="Ministere de la Transition ecologique / BRGM",
        fichier=output_path,
    )

    return output_path
