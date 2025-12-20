from __future__ import annotations

"""Concurrent frame bus: producer decodes, workers extract features.

Enabled when env ARES_CONCURRENCY=1.
Simplifies to one worker thread for vision features now; can extend.
"""

import os
import threading
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List
import cv2
import numpy as np

@dataclass
class FramePayload:
    frame_idx: int
    frame: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    features: Dict[str, float]


def _extract(gray: np.ndarray) -> tuple[Dict[str, float], np.ndarray]:
    mean_intensity = float(np.mean(gray)) / 255.0
    std_intensity = float(np.std(gray)) / 255.0
    edges = cv2.Canny(gray, 80, 200)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size or 1)
    return {
        "mean_intensity": mean_intensity,
        "std_intensity": std_intensity,
        "edge_density": edge_density,
    }, edges


def concurrent_frame_bus(path: Path, stride: int = 1, downscale: float = 0.75, max_queue: int = 64) -> Generator[FramePayload, None, None]:
    if os.getenv("ARES_CONCURRENCY", "0") != "1":
        raise RuntimeError("Concurrency disabled (set ARES_CONCURRENCY=1)")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open media file: {path}")
    q: "queue.Queue[tuple[int, np.ndarray]]" = queue.Queue(maxsize=max_queue)
    stop_flag = threading.Event()

    def producer():
        idx = 0
        try:
            while not stop_flag.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % stride == 0:
                    if downscale != 1.0:
                        frame = cv2.resize(frame, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
                    q.put((idx, frame))
                idx += 1
        finally:
            stop_flag.set()
            cap.release()

    prod_thread = threading.Thread(target=producer, daemon=True)
    prod_thread.start()

    while not (stop_flag.is_set() and q.empty()):
        try:
            idx, frame = q.get(timeout=0.2)
        except queue.Empty:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        feats, edges = _extract(gray)
        yield FramePayload(frame_idx=idx, frame=frame, gray=gray, edges=edges, features=feats)
    prod_thread.join(timeout=1.0)
