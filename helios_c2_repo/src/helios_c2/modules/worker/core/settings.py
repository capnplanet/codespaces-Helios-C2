from __future__ import annotations

"""Minimal settings stub for motion/detection thresholds."""

from dataclasses import dataclass


@dataclass
class Settings:
    detection_min_area: float = 0.001
    detection_min_aspect: float = 0.25
    detection_max_aspect: float = 0.9
    motion_delta_threshold: float = 1.5


def load_settings() -> Settings:
    return Settings()
