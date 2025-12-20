from __future__ import annotations

from hashlib import sha256
from pathlib import Path


SOUND_LIBRARY = [
    {"label": "small_arms_discharge", "confidence": 0.62},
    {"label": "vehicle_engine_high_rpm", "confidence": 0.58},
    {"label": "crowd_alarm", "confidence": 0.54},
    {"label": "radio_chatter", "confidence": 0.61},
]


def detect_sounds(path: Path) -> list[dict]:
    digest = sha256(str(path).encode("utf-8")).hexdigest()
    idx = int(digest[8:12], 16) % len(SOUND_LIBRARY)
    secondary = (idx + 1) % len(SOUND_LIBRARY)
    return [SOUND_LIBRARY[idx], SOUND_LIBRARY[secondary]]
