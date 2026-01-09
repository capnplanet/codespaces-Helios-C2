import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
import uuid

import numpy as np

from ..features.fusion import FusedFeatures


@dataclass
class Observation:
    entity_id: str
    timestamp: float
    camera_id: str
    fused_features: FusedFeatures

    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "timestamp": float(self.timestamp),
            "camera_id": self.camera_id,
            "fused_features": self.fused_features.to_dict(),
        }

    @staticmethod
    def from_dict(payload: Dict) -> "Observation":
        return Observation(
            entity_id=str(payload.get("entity_id")),
            timestamp=float(payload.get("timestamp", 0.0)),
            camera_id=str(payload.get("camera_id", "")),
            fused_features=FusedFeatures.from_dict(payload.get("fused_features", {})),
        )


@dataclass
class EntityProfile:
    entity_id: str
    observations: List[Observation] = field(default_factory=list)

    @property
    def feature_matrix(self) -> np.ndarray:
        if not self.observations:
            return np.zeros((0, 1), dtype=np.float32)
        return np.stack(
            [obs.fused_features.as_array() for obs in self.observations], axis=0
        )

    def centroid(self) -> np.ndarray:
        fm = self.feature_matrix
        if fm.size == 0:
            return np.zeros(1, dtype=np.float32)
        return fm.mean(axis=0)

    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "observations": [obs.to_dict() for obs in self.observations],
        }

    @staticmethod
    def from_dict(payload: Dict) -> "EntityProfile":
        profile = EntityProfile(entity_id=str(payload.get("entity_id")))
        obs_payloads = payload.get("observations", []) or []
        for obs_payload in obs_payloads:
            profile.observations.append(Observation.from_dict(obs_payload))
        return profile


class EntityStore:
    """Simple in-memory entity store.

    Swap out for a database-backed implementation for production use.
    """

    def __init__(self):
        self._entities: Dict[str, EntityProfile] = {}

    def create_entity(self) -> EntityProfile:
        entity_id = str(uuid.uuid4())
        profile = EntityProfile(entity_id=entity_id)
        self._entities[entity_id] = profile
        return profile

    def add_observation(
        self, entity_id: str, timestamp: float, camera_id: str, fused: FusedFeatures
    ) -> Observation:
        profile = self._entities[entity_id]
        obs = Observation(
            entity_id=entity_id,
            timestamp=timestamp,
            camera_id=camera_id,
            fused_features=fused,
        )
        profile.observations.append(obs)
        return obs

    def get_all_profiles(self) -> List[EntityProfile]:
        return list(self._entities.values())

    def get_profile(self, entity_id: str) -> EntityProfile | None:
        return self._entities.get(entity_id)

    def save_json(self, path: Path | str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entities": [profile.to_dict() for profile in self.get_all_profiles()],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load_json(cls, path: Path | str) -> "EntityStore":
        in_path = Path(path)
        if not in_path.exists():
            raise FileNotFoundError(f"Entity store file not found: {in_path}")
        with open(in_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        store = cls()
        for profile_payload in payload.get("entities", []) or []:
            profile = EntityProfile.from_dict(profile_payload)
            store._entities[profile.entity_id] = profile
        return store
