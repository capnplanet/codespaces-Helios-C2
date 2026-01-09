from collections import defaultdict
from typing import Dict, List

import numpy as np

from ..utils.time_utils import hour_of_day
from .entity_store import EntityProfile, EntityStore


def summarize_entity_pattern(profile: EntityProfile) -> Dict:
    if not profile.observations:
        return {
            "entity_id": profile.entity_id,
            "num_observations": 0,
            "cameras_histogram": {},
            "hours_histogram": {},
            "dominant_camera": None,
            "dominant_hour_of_day": None,
            "time_span_seconds": 0.0,
        }

    times = np.array([obs.timestamp for obs in profile.observations], dtype=float)

    by_camera = defaultdict(int)
    by_hour = defaultdict(int)
    for obs in profile.observations:
        by_camera[obs.camera_id] += 1
        by_hour[hour_of_day(obs.timestamp)] += 1

    dominant_camera = max(by_camera.items(), key=lambda x: x[1])[0]
    dominant_hour = max(by_hour.items(), key=lambda x: x[1])[0]

    return {
        "entity_id": profile.entity_id,
        "num_observations": len(profile.observations),
        "cameras_histogram": dict(by_camera),
        "hours_histogram": dict(by_hour),
        "dominant_camera": dominant_camera,
        "dominant_hour_of_day": dominant_hour,
        "time_span_seconds": float(times.max() - times.min())
        if len(times) > 1
        else 0.0,
    }


def summarize_all_entities(store: EntityStore) -> List[Dict]:
    return [summarize_entity_pattern(p) for p in store.get_all_profiles()]
