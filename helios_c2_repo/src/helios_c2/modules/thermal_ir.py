from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import cv2
import numpy as np

from .worker.modelhub import registry

THERMAL_MODEL = registry.thermal_model()


@dataclass
class ThermalFrame:
    frame: int
    label: str
    probability: float
    features: Dict[str, float]
    hotspot_pixels: float

    def as_event_fragment(self) -> Dict[str, object]:
        return {
            "frame": self.frame,
            "label": self.label,
            "confidence": round(self.probability, 3),
            "features": self.features,
            "hotspot_pixels": self.hotspot_pixels,
        }


def _extract_features(frame: np.ndarray) -> Dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    normalized = gray.astype(np.float32) / 255.0
    mean_heat = float(np.mean(normalized))
    heat_std = float(np.std(normalized))
    hotspot_mask = normalized > 0.75
    hotspot_ratio = float(np.count_nonzero(hotspot_mask)) / float(normalized.size or 1)
    return {
        "mean_heat": mean_heat,
        "heat_std": heat_std,
        "hotspot_ratio": hotspot_ratio,
    }


def _classify(features: Dict[str, float]) -> ThermalFrame:
    probabilities = THERMAL_MODEL.classify(features)
    ranked = sorted(probabilities, key=lambda item: item["probability"], reverse=True)
    top = ranked[0] if ranked else {"label": "ambient", "probability": 1.0}
    return ThermalFrame(
        frame=0,
        label=top.get("label", "ambient"),
        probability=float(top.get("probability", 0.0)),
        features=features,
        hotspot_pixels=features["hotspot_ratio"],
    )


def analyze(path: Path, stride: int = 3) -> Dict[str, object]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open media file for thermal analysis: {path}")

    frames: List[ThermalFrame] = []
    frame_idx = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            if frame_idx % stride == 0:
                features = _extract_features(frame)
                tf = _classify(features)
                frames.append(ThermalFrame(
                    frame=frame_idx,
                    label=tf.label,
                    probability=tf.probability,
                    features=features,
                    hotspot_pixels=tf.hotspot_pixels,
                ))
            frame_idx += 1
    finally:
        capture.release()

    if not frames:
        return {"frames": [], "summary": {"frame_count": 0, "max_probability": 0.0, "hotspot_ratio_mean": 0.0}}

    probabilities = np.array([fr.probability for fr in frames], dtype=np.float32)
    hotspot_ratios = np.array([fr.hotspot_pixels for fr in frames], dtype=np.float32)
    top_frame = max(frames, key=lambda fr: fr.probability)

    summary = {
        "frame_count": len(frames),
        "max_probability": float(np.max(probabilities)),
        "mean_probability": float(np.mean(probabilities)),
        "hotspot_ratio_mean": float(np.mean(hotspot_ratios)),
        "top_label": top_frame.label,
        "top_frame": top_frame.frame,
    }

    return {
        "frames": [fr.as_event_fragment() for fr in frames],
        "summary": summary,
    }