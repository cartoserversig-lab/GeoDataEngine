"""Generation du fichier de metadonnees du projet."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Repertoire de sortie par defaut : data/metadata a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_METADATA_DIR = Path(__file__).resolve().parents[2] / "data" / "metadata"
DEFAULT_METADATA_FILE = "metadata.json"


def record_layer_metadata(
    layer: str,
    source: str,
    producteur: str,
    fichier: str | Path,
    crs: str,
    resolution: float | None = None,
    traitements: list[str] | None = None,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    metadata_file: str = DEFAULT_METADATA_FILE,
) -> Path:
    """Ajoute un enregistrement de metadonnees pour une couche telechargee.

    Champs conformes au CDC (source, date de telechargement, producteur,
    resolution, systeme de coordonnees, traitements appliques). Chaque appel
    ajoute une entree a data/metadata/metadata.json (cree si absent).
    """
    metadata_dir = Path(metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / metadata_file

    records: list[dict[str, Any]] = []
    if metadata_path.exists():
        records = json.loads(metadata_path.read_text(encoding="utf-8"))

    records.append(
        {
            "couche": layer,
            "source": source,
            "producteur": producteur,
            "fichier": str(fichier),
            "date_telechargement": datetime.now(timezone.utc).isoformat(),
            "crs": crs,
            "resolution": resolution,
            "traitements_appliques": traitements or [],
        }
    )

    metadata_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata_path
