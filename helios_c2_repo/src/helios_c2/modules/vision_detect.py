from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2
import numpy as np

from .worker.modelhub import registry

VISION_MODEL = registry.vision_model()

# Quick performance tuning defaults
DEFAULT_DOWNSCALE = 0.75  # scale factor for feature extraction
MAX_LABELS = 3  # keep top-N labels above threshold

def _prepare_frame(frame: np.ndarray, downscale: float) -> tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Unified core feature extraction with optional downscale.
    Returns (gray, edges, features dict).
    """
    if downscale != 1.0:
        frame = cv2.resize(frame, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 200)
    mean_intensity = float(np.mean(gray)) / 255.0
    std_intensity = float(np.std(gray)) / 255.0
    edge_density = float(np.count_nonzero(edges)) / float(edges.size or 1)
    return gray, edges, {
        "mean_intensity": mean_intensity,
        "std_intensity": std_intensity,
        "edge_density": edge_density,
    }


def _extract_features(frame: np.ndarray) -> tuple[Dict[str, float], np.ndarray]:  # backward compatible
    _, edges, features = _prepare_frame(frame, 1.0)
    return features, edges


def _contour_bbox(edges: np.ndarray, frame_shape: tuple[int, int, int]) -> List[float]:
    height, width = frame_shape[:2]
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return [0.05, 0.05, 0.95, 0.95]
    contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(contour)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    return [float(x)/width, float(y)/height, float(x2)/width, float(y2)/height]

def _refine_person_bbox(edges: np.ndarray, frame: np.ndarray) -> List[float]:
    """Original refinement: kept for backward compatibility (non-persistent)."""
    h, w = frame.shape[:2]
    kernel = np.ones((3, 3), np.uint8)
    proc = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(proc, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _contour_bbox(edges, frame.shape)
    frame_area = float(w * h or 1)
    candidates: List[Tuple[float, List[float]]] = []
    for c in contours[:500]:
        area = float(cv2.contourArea(c))
        if area < 0.002 * frame_area or area > 0.2 * frame_area:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = (cw / float(ch or 1))
        if aspect < 0.25 or aspect > 0.8:
            continue
        score = (1.0 - aspect) + (0.05 - abs(area / frame_area - 0.05))
        candidates.append((score, [float(x)/w, float(y)/h, float(x+cw)/w, float(y+ch)/h]))
    if not candidates:
        return _contour_bbox(edges, frame.shape)
    return max(candidates, key=lambda t: t[0])[1]


def _determine_bbox(edges: np.ndarray, frame: np.ndarray, label: str | None = None) -> List[float]:
    strategy = (VISION_MODEL.bbox_strategy or "edge_contour").lower()
    if label == "person":
        return _refine_person_bbox(edges, frame)
    if strategy == "edge_contour":
        return _contour_bbox(edges, frame.shape)
    return [0.05, 0.05, 0.95, 0.95]

def _motion_gate(prev_gray: np.ndarray | None, gray: np.ndarray, frame_idx: int, last_proc: int, diff_thresh: float, min_interval: int) -> tuple[bool, int]:
    if prev_gray is None:
        return True, frame_idx
    if frame_idx - last_proc < min_interval:
        # enforce spacing
        return False, last_proc
    diff = cv2.absdiff(gray, prev_gray)
    mse = float(np.mean(diff))
    if mse < diff_thresh:
        return False, last_proc
    return True, frame_idx


def detect_frames(path: Path, stride: int = 16, downscale: float = DEFAULT_DOWNSCALE,
                  motion_gate: bool = False, diff_thresh: float = 4.0, min_interval: int = 2) -> Iterable[Dict[str, object]]:
    """Frame-level detection with optional downscale and motion gating.

    - downscale: resize factor for faster feature extraction
    - motion_gate: if True, skips frames with low pixel change (MSE < diff_thresh) within min_interval
    - Returns multiple detections (top-N above threshold) per frame.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open media file: {path}")

    frame_idx = 0
    last_processed = -999
    prev_gray = None
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            if frame_idx % stride == 0:
                gray, edges, features = _prepare_frame(frame, downscale)
                if motion_gate:
                    proceed, last_processed = _motion_gate(prev_gray, gray, frame_idx, last_processed, diff_thresh, min_interval)
                    if not proceed:
                        frame_idx += 1
                        prev_gray = gray
                        continue
                probabilities = VISION_MODEL.classify(features)
                ranked = [p for p in sorted(probabilities, key=lambda item: item["probability"], reverse=True)
                          if p["probability"] >= VISION_MODEL.min_probability][:MAX_LABELS]
                if not ranked:
                    frame_idx += 1
                    prev_gray = gray
                    continue
                # single contour computation reused for non-person labels to avoid recomputation
                base_bbox = _contour_bbox(edges, frame.shape)
                dets = []
                for p in ranked:
                    label = p.get("label", "object_of_interest")
                    bbox = persistent_person_detector.detect(edges, frame, frame_idx) if label == "person" else base_bbox
                    dets.append({
                        "label": label,
                        "confidence": round(float(p["probability"]), 3),
                        "bbox": bbox,
                    })
                yield {
                    "frame": frame_idx,
                    "detections": dets,
                    "features": features,
                }
                last_processed = frame_idx
                prev_gray = gray
            frame_idx += 1
    finally:
        capture.release()


# ---------------------------------------------------------------------------
# Persistent + motion-gated heuristic person detector
# ---------------------------------------------------------------------------
from .worker.core.settings import load_settings  # deferred import to avoid cycles


class HeuristicPersonDetector:
    def __init__(self) -> None:
        self.prev_bbox: List[float] | None = None
        self.prev_gray: np.ndarray | None = None
        self.last_frame: int = -999
        s = load_settings()
        self.min_area = s.detection_min_area
        self.min_aspect = s.detection_min_aspect
        self.max_aspect = s.detection_max_aspect
        self.motion_delta_thresh = s.motion_delta_threshold
        self.reuse_interval = 5  # frames

    def detect(self, edges: np.ndarray, frame: np.ndarray, frame_idx: int) -> List[float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Motion gate reuse
        if self.prev_gray is not None and self.prev_bbox is not None:
            diff = cv2.absdiff(gray, self.prev_gray)
            mse = float(np.mean(diff))
            if mse < self.motion_delta_thresh and frame_idx - self.last_frame < self.reuse_interval:
                return self.prev_bbox
        h, w = frame.shape[:2]
        search_edges = edges
        # ROI persistence: restrict search to inflated previous bbox if exists
        if self.prev_bbox is not None:
            px, py, px2, py2 = self.prev_bbox
            x = int(px * w)
            y = int(py * h)
            x2 = int(px2 * w)
            y2 = int(py2 * h)
            # inflate region by 15%
            margin_x = int(0.15 * (x2 - x + 1))
            margin_y = int(0.15 * (y2 - y + 1))
            rx = max(0, x - margin_x)
            ry = max(0, y - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)
            roi = search_edges[ry:ry2, rx:rx2]
        else:
            rx, ry, rx2, ry2 = 0, 0, w, h
            roi = search_edges
        kernel = np.ones((3, 3), np.uint8)
        proc = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(proc, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        chosen: List[float] | None = None
        frame_area = float(w * h or 1)
        for c in contours[:300]:
            area = float(cv2.contourArea(c))
            if area < self.min_area or area > 0.25 * frame_area:
                continue
            x0, y0, cw, ch = cv2.boundingRect(c)
            # adjust to full-frame coordinates
            x_abs = x0 + rx
            y_abs = y0 + ry
            aspect = cw / float(ch or 1)
            if aspect < self.min_aspect or aspect > self.max_aspect:
                continue
            chosen = [x_abs / w, y_abs / h, (x_abs + cw) / w, (y_abs + ch) / h]
            break
        if chosen is None:
            # fallback full-frame
            chosen = _refine_person_bbox(edges, frame)
        self.prev_bbox = chosen
        self.prev_gray = gray
        self.last_frame = frame_idx
        return chosen


persistent_person_detector = HeuristicPersonDetector()
