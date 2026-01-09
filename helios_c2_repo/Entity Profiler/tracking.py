from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Track:
    track_id: int
    bbox: Tuple[int, int, int, int]
    score: float
    last_seen_ts: float
    embedding: np.ndarray
    frame_index: int


class CosineTracker:
    """Lightweight tracker using cosine similarity on embeddings.

    Designed for CPU-friendly pipelines: it maintains short-lived tracks and
    assigns new detections to existing tracks if similarity exceeds a threshold.
    """

    def __init__(self, sim_threshold: float = 0.7, max_age_seconds: float = 3.0):
        self.sim_threshold = sim_threshold
        self.max_age_seconds = max_age_seconds
        self._tracks: List[Track] = []
        self._next_id = 1

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        if a.size == 0 or b.size == 0:
            return 0.0
        na = np.linalg.norm(a) + 1e-8
        nb = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (na * nb))

    def _prune(self, now_ts: float) -> None:
        self._tracks = [t for t in self._tracks if now_ts - t.last_seen_ts <= self.max_age_seconds]

    def update(
        self,
        detections: List[Tuple[int, int, int, int, float]],
        embeddings: List[np.ndarray],
        frame_index: int,
        now_ts: float,
    ) -> List[Track]:
        """Update tracker and return current tracks.

        Args:
            detections: list of (x,y,w,h,score) tuples.
            embeddings: list of np.ndarray embeddings aligned with detections.
        """
        assert len(detections) == len(embeddings)
        self._prune(now_ts)

        assigned_tracks: List[Track] = []
        for det, emb in zip(detections, embeddings):
            x, y, w, h, score = det
            if emb is None:
                emb = np.zeros(1, dtype=np.float32)
            best_track = None
            best_sim = self.sim_threshold
            for t in self._tracks:
                sim = self._cosine(t.embedding, emb)
                if sim >= best_sim:
                    best_sim = sim
                    best_track = t
            if best_track is None:
                track = Track(
                    track_id=self._next_id,
                    bbox=(x, y, w, h),
                    score=score,
                    last_seen_ts=now_ts,
                    embedding=emb.astype(np.float32),
                    frame_index=frame_index,
                )
                self._next_id += 1
                self._tracks.append(track)
                assigned_tracks.append(track)
            else:
                best_track.bbox = (x, y, w, h)
                best_track.score = score
                best_track.last_seen_ts = now_ts
                best_track.embedding = emb.astype(np.float32)
                best_track.frame_index = frame_index
                assigned_tracks.append(best_track)

        return assigned_tracks

    def tracks(self) -> List[Track]:
        return list(self._tracks)
