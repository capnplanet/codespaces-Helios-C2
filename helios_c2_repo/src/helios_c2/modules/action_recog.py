from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

from .worker.modelhub import registry

ACTION_MODEL = registry.action_model()


def _compute_motion(path: Path) -> Dict[str, float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open media file for action classification: {path}")

    prev_gray = None
    motion_series: List[float] = []
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                motion_val = float(np.mean(diff)) / 255.0
                motion_series.append(motion_val)
            prev_gray = gray
    finally:
        capture.release()

    if not motion_series:
        return {"mean_motion": 0.0, "motion_std": 0.0, "max_motion": 0.0}

    motion_array = np.array(motion_series, dtype=np.float32)
    features = {
        "mean_motion": float(np.mean(motion_array)),
        "motion_std": float(np.std(motion_array)),
        "max_motion": float(np.max(motion_array)),
    }
    return features


def classify_actions(path: Path) -> List[Dict[str, object]]:
    features = _compute_motion(path)
    predictions = ACTION_MODEL.classify(features)
    ranked = sorted(predictions, key=lambda item: item["probability"], reverse=True)
    top = ranked[0] if ranked else {"label": "patrol_idle", "probability": 1.0}
    return [
        {
            "label": top.get("label", "patrol_idle"),
            "confidence": round(float(top.get("probability", 0.0)), 3),
            "features": features,
        }
    ]
