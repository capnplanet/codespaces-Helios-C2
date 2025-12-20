from __future__ import annotations

"""Unified frame bus for shared decode + feature extraction.

Provides a generator that yields per-frame payloads with cached grayscale,
edge map, and base vision features so multiple modules (vision, gait,
interaction, thermal) can reuse data without re-decoding the video.

Supports:
 - stride: base frame skipping
 - downscale: resize for performance
 - motion gating: skip frames with low pixel delta
 - early summarization hook (optional predicate)
 - optional batch buffering
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Generator, Iterable, List, Optional

import cv2
import numpy as np


@dataclass
class FramePayload:
    frame_idx: int
    frame: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    features: Dict[str, float]


def _extract(gray: np.ndarray) -> Dict[str, float]:
    mean_intensity = float(np.mean(gray)) / 255.0
    std_intensity = float(np.std(gray)) / 255.0
    edges = cv2.Canny(gray, 80, 200)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size or 1)
    return {
        "mean_intensity": mean_intensity,
        "std_intensity": std_intensity,
        "edge_density": edge_density,
    }, edges


def frame_bus(
    path: Path,
    stride: int = 1,
    downscale: float = 1.0,
    motion_gate: bool = False,
    diff_thresh: float = 4.0,
    min_interval: int = 2,
    early_stop: Optional[Callable[[List[FramePayload]], bool]] = None,
    max_frames: Optional[int] = None,
    stabilize: bool = False,
) -> Generator[FramePayload, None, None]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open media file: {path}")

    prev_gray = None
    last_processed = -999
    processed: List[FramePayload] = []
    frame_idx = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            if max_frames is not None and len(processed) >= max_frames:
                break
            if frame_idx % stride != 0:
                frame_idx += 1
                continue
            if downscale != 1.0:
                frame = cv2.resize(frame, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if stabilize and prev_gray is not None:
                # Estimate translation using feature matching (ORB)
                orb = cv2.ORB_create(256)
                kp1, des1 = orb.detectAndCompute(prev_gray, None)
                kp2, des2 = orb.detectAndCompute(gray, None)
                if des1 is not None and des2 is not None and len(kp1) > 8 and len(kp2) > 8:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                    matches = bf.match(des1, des2)
                    matches = sorted(matches, key=lambda m: m.distance)[:40]
                    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches])
                    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches])
                    if len(pts1) >= 8:
                        # Estimate affine transform (fallback to identity)
                        M, inliers = cv2.estimateAffinePartial2D(pts2, pts1, method=cv2.RANSAC, ransacReprojThreshold=3.0)
                        if M is not None:
                            frame = cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0]))
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if motion_gate:
                if prev_gray is not None and frame_idx - last_processed < min_interval:
                    frame_idx += 1
                    prev_gray = gray
                    continue
                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    mse = float(np.mean(diff))
                    if mse < diff_thresh:
                        frame_idx += 1
                        prev_gray = gray
                        continue
            features, edges = _extract(gray)
            payload = FramePayload(
                frame_idx=frame_idx,
                frame=frame,
                gray=gray,
                edges=edges,
                features=features,
            )
            processed.append(payload)
            yield payload
            last_processed = frame_idx
            prev_gray = gray
            frame_idx += 1
            if early_stop and early_stop(processed):
                break
    finally:
        capture.release()


def stable_motion_stop(window: int = 60, speed_epsilon: float = 1e-4) -> Callable[[List[FramePayload]], bool]:
    """Return predicate that signals early stop when edge density variance stabilizes.
    Simplistic heuristic to demonstrate early summarization capability.
    """
    def _predicate(buff: List[FramePayload]) -> bool:
        if len(buff) < window:
            return False
        densities = [p.features.get("edge_density", 0.0) for p in buff[-window:]]
        var = float(np.var(densities))
        return var < speed_epsilon
    return _predicate
