from typing import List, Optional

import numpy as np

from ..config import load_config
from ..features.fusion import FusedFeatures
from .entity_store import EntityProfile, EntityStore


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


class EntityClusteringEngine:
    """Assign new observations to entities using centroid distance."""

    def __init__(self, store: EntityStore):
        self.store = store
        self.cfg = load_config()

    def _best_match_entity(self, fused_vec: np.ndarray) -> Optional[EntityProfile]:
        candidates: List[EntityProfile] = self.store.get_all_profiles()
        if not candidates:
            return None
        dists = [(p, euclidean_distance(p.centroid(), fused_vec)) for p in candidates]
        dists.sort(key=lambda x: x[1])
        best_profile, best_dist = dists[0]
        if best_dist <= self.cfg.fused_distance_threshold:
            return best_profile
        return None

    def assign_observation(
        self, timestamp: float, camera_id: str, fused: FusedFeatures
    ) -> EntityProfile:
        fused_vec = fused.as_array()
        profile = self._best_match_entity(fused_vec)
        if profile is None:
            profile = self.store.create_entity()
        self.store.add_observation(profile.entity_id, timestamp, camera_id, fused)
        return profile
