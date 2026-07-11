"""Generation du fichier de metadonnees du projet."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Repertoire de sortie par defaut : data/metadata a la racine du depot.
# A terme, ce chemin sera fourni par core/project.py (gestion du projet) plutot que fige ici.
DEFAULT_METADATA_DIR = Path(__file__).resolve().parents[2] / "data" / "metadata"
DEFAULT_METADATA_FILE = "metadata.json"


def record_layer_metadata(
    layer: str,
    source: str,
    producteur: str,
    fichier: str | Path,
    crs: str | None = None,
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
            "fichier": str(Path(fichier).resolve()),
            "date_telechargement": datetime.now(timezone.utc).isoformat(),
            "crs": crs,
            "resolution": resolution,
            "traitements_appliques": traitements or [],
        }
    )

    metadata_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata_path


def find_metadata_record(
    fichier: str | Path,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    metadata_file: str = DEFAULT_METADATA_FILE,
) -> dict[str, Any] | None:
    """Retrouve le dernier enregistrement de metadonnees correspondant a un fichier.

    Utilise pour propager source/producteur/CRS/resolution lors du
    chainage d'un traitement (decoupage, reprojection, Lidar...) sur une
    couche deja enregistree, sans avoir a les re-preciser manuellement.
    Retourne None si aucun enregistrement ne correspond.

    La comparaison se fait sur le chemin resolu (absolu), pour ne pas
    manquer une correspondance a cause d'un chemin relatif ecrit
    differemment d'un appel a l'autre.
    """
    metadata_path = Path(metadata_dir) / metadata_file
    if not metadata_path.exists():
        return None

    records: list[dict[str, Any]] = json.loads(metadata_path.read_text(encoding="utf-8"))
    target = str(Path(fichier).resolve())
    matches = [r for r in records if r["fichier"] == target]
    return matches[-1] if matches else None


def record_processing(
    input_path: str | Path,
    output_path: str | Path,
    traitement: str,
    resolution: float | None = None,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    metadata_file: str = DEFAULT_METADATA_FILE,
) -> Path:
    """Enregistre un traitement applique a une couche deja suivie dans les metadonnees.

    Retrouve l'enregistrement existant de input_path (couche brute ou deja
    traitee) pour en heriter couche/source/producteur/crs/resolution, et
    ajoute un nouvel enregistrement pour output_path avec traitement
    ajoute a la liste des traitements appliques cumulee depuis
    l'enregistrement source (CDC section 12).

    resolution, si fourni, remplace la resolution heritee (utile quand le
    traitement produit un raster a une resolution propre, ex. MNT/MNS/MNH
    issus d'un nuage de points qui n'a pas de resolution intrinseque).

    Si aucun enregistrement n'est retrouve pour input_path (couche non
    suivie, ex. fixture de test ou fichier intermediaire), enregistre une
    entree minimale avec source/producteur inconnus plutot que d'echouer :
    la tracabilite du traitement lui-meme reste assuree.
    """
    source_record = find_metadata_record(input_path, metadata_dir=metadata_dir, metadata_file=metadata_file)

    if source_record is None:
        logger.warning(
            "Aucun enregistrement de metadonnees trouve pour %s ; enregistrement minimal pour %s.",
            input_path,
            output_path,
        )
        return record_layer_metadata(
            layer=Path(output_path).stem,
            source="inconnue",
            producteur="inconnue",
            fichier=output_path,
            resolution=resolution,
            traitements=[traitement],
            metadata_dir=metadata_dir,
            metadata_file=metadata_file,
        )

    traitements = list(source_record.get("traitements_appliques", [])) + [traitement]
    return record_layer_metadata(
        layer=source_record["couche"],
        source=source_record["source"],
        producteur=source_record["producteur"],
        fichier=output_path,
        crs=source_record.get("crs"),
        resolution=resolution if resolution is not None else source_record.get("resolution"),
        traitements=traitements,
        metadata_dir=metadata_dir,
        metadata_file=metadata_file,
    )
