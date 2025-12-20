from __future__ import annotations

"""Non-identifying coarse appearance-motion signature utilities.

Creates a short hash from quantized coarse features to allow session-level
association WITHOUT asserting identity. Highly unstable across lighting/clothing.
"""

import hashlib
from typing import Dict, List, Tuple
import numpy as np
import cv2

try:
    import mediapipe as mp  # type: ignore
    _POSE = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                   enable_segmentation=False, min_detection_confidence=0.5,
                                   min_tracking_confidence=0.5)
    _POSE_LANDMARKS = {
        'left_shoulder': mp.solutions.pose.PoseLandmark.LEFT_SHOULDER,
        'right_shoulder': mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER,
        'left_hip': mp.solutions.pose.PoseLandmark.LEFT_HIP,
        'right_hip': mp.solutions.pose.PoseLandmark.RIGHT_HIP,
    }
except Exception:  # mediapipe optional
    _POSE = None
    _POSE_LANDMARKS = {}


def extract_upper_pose_landmarks(frame) -> Dict[str, Tuple[float, float, float]]:
    """Extract a minimal set of upper-body landmarks for coverage scoring.
    Returns empty dict if mediapipe unavailable or no landmarks.
    """
    if _POSE is None:
        return {}
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = _POSE.process(rgb)
    if not res.pose_landmarks:
        return {}
    lm_dict: Dict[str, Tuple[float, float, float]] = {}
    for name, enum_val in _POSE_LANDMARKS.items():
        lm = res.pose_landmarks.landmark[enum_val]
        lm_dict[name] = (lm.x, lm.y, lm.visibility)
    return lm_dict


def landmark_coverage(lm_dict: Dict[str, Tuple[float, float, float]], vis_thresh: float = 0.5) -> float:
    if not lm_dict:
        return 0.0
    valid = sum(1 for _, (_, _, v) in lm_dict.items() if v >= vis_thresh)
    return valid / float(len(lm_dict))


def rgb_histogram(frame, bbox_norm, bins: int = 4) -> List[int]:
    """Compute coarse RGB histogram for region defined by normalized bbox (x1,y1,x2,y2)."""
    x1,y1,x2,y2 = bbox_norm
    h,w = frame.shape[:2]
    x1i = max(0, int(x1 * w)); x2i = max(0, min(w, int(x2 * w)))
    y1i = max(0, int(y1 * h)); y2i = max(0, min(h, int(y2 * h)))
    if x2i <= x1i or y2i <= y1i:
        return [0] * (bins * 3)
    roi = frame[y1i:y2i, x1i:x2i]
    feats: List[int] = []
    for c in range(3):
        hist, _ = np.histogram(roi[:, :, c], bins=bins, range=(0, 255))
        feats.extend(hist.astype(int).tolist())
    return feats


def quantize(value: float, bins: int, vmin: float, vmax: float) -> int:
    if value < vmin:
        value = vmin
    if value > vmax:
        value = vmax
    step = (vmax - vmin) / float(bins)
    if step <= 0:
        return 0
    return int((value - vmin) // step)


def build_signature(features: Dict[str, float], rgb_hist: List[int]) -> Tuple[str, List[int]]:
    """Quantize selected features + histogram into a short hash.
    Returns (hash_prefix, quantized_vector).
    """
    vec: List[int] = []
    vec.append(quantize(features.get('height_norm', 0.0), 10, 0.2, 1.0))
    vec.append(quantize(features.get('speed_norm_mean', 0.0), 12, 0.0, 0.05))
    vec.append(quantize(features.get('edge_density_mean', 0.0), 10, 0.0, 0.15))
    vec.append(quantize(features.get('landmark_cov', 0.0), 5, 0.0, 1.0))
    # limit first 12 bins for brevity
    for v in rgb_hist[:12]:
        vec.append(quantize(float(v), 8, 0.0, 5000.0))
    raw = ','.join(map(str, vec))
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]
    return digest, vec
