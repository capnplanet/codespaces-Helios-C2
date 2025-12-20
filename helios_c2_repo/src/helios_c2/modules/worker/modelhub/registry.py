from __future__ import annotations

"""Lightweight model registry stubs for Helios module adapters.
Provides deterministic classify() outputs so the pipeline can run without
external ML dependencies.
"""

from dataclasses import dataclass
from typing import Dict, List
import random


@dataclass
class _Model:
    label: str
    min_probability: float = 0.2
    bbox_strategy: str = "edge_contour"

    def classify(self, features: Dict[str, float]) -> List[Dict[str, float]]:
        # Deterministic pseudo probabilities based on feature hash for stability.
        seed = hash(tuple(sorted(features.items()))) & 0xFFFFFFFF
        rng = random.Random(seed)
        base = max(0.2, min(0.95, features.get("edge_density", 0.5) + 0.1))
        return [
            {"label": self.label, "probability": base},
            {"label": f"{self.label}_alt", "probability": max(0.1, base - 0.2 * rng.random())},
        ]


def vision_model() -> _Model:
    return _Model(label="person", min_probability=0.25, bbox_strategy="edge_contour")


def action_model() -> _Model:
    return _Model(label="patrol_idle", min_probability=0.2)


def thermal_model() -> _Model:
    return _Model(label="hotspot", min_probability=0.2)


def model_provenance() -> Dict[str, str]:
    return {
        "vision": "stub-vision-0.1",
        "action": "stub-action-0.1",
        "thermal": "stub-thermal-0.1",
    }
