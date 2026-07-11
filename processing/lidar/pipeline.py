"""Orchestration des traitements PDAL (construction et execution de pipelines)."""

from __future__ import annotations

import json
import logging

import pdal

logger = logging.getLogger(__name__)


class LidarProcessingError(RuntimeError):
    """Erreur lors de l'execution d'un pipeline PDAL sur un nuage de points."""


def run_pipeline(stages: list[dict]) -> tuple[pdal.Pipeline, int]:
    """Execute un pipeline PDAL defini par une liste d'etapes (stages).

    Retourne le pipeline execute (permettant de recuperer les arrays de
    points via pipeline.arrays si besoin) et le nombre de points traites.

    Leve LidarProcessingError si l'execution du pipeline echoue.
    """
    pipeline = pdal.Pipeline(json.dumps(stages))
    try:
        num_points = pipeline.execute()
    except RuntimeError as exc:
        raise LidarProcessingError(f"Echec de l'execution du pipeline PDAL : {exc}") from exc
    return pipeline, num_points
