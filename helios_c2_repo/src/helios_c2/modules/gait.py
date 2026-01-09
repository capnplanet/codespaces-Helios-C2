from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np

# Performance tuning constants
MIN_TRACK_LENGTH = 5
SECOND_PASS_LINK_DIST = 0.18
PRIMARY_LINK_DIST = 0.12
MIN_STABLE_LENGTH = 20  # cadence requires at least this length


@dataclass
class Track:
    id: str
    frames: List[int]
    bboxes: List[List[float]]  # [x1,y1,x2,y2] normalized

    def centroids(self) -> np.ndarray:
        c = []
        for b in self.bboxes:
            x1, y1, x2, y2 = b
            c.append([(x1 + x2) / 2.0, (y1 + y2) / 2.0])
        return np.array(c, dtype=np.float32)

    def aspects(self) -> np.ndarray:
        a = []
        for b in self.bboxes:
            x1, y1, x2, y2 = b
            w = max(1e-6, x2 - x1)
            h = max(1e-6, y2 - y1)
            a.append(w / h)
        return np.array(a, dtype=np.float32)

    def heights(self) -> np.ndarray:
        hts = []
        for b in self.bboxes:
            x1, y1, x2, y2 = b
            hts.append(max(1e-6, y2 - y1))
        return np.array(hts, dtype=np.float32)


def _link_tracks(detections: Iterable[Dict[str, object]], max_link_dist: float = PRIMARY_LINK_DIST) -> List[Track]:
    """Vectorized nearest-neighbor linking across consecutive frames.
    Only links frame-to-frame (no skipping); persons only.
    """
    # Collect per-frame person detections
    frame_records: List[Tuple[int, List[List[float]]]] = []
    for item in detections:
        frame_idx = int(item.get("frame", 0))
        bbs = [d.get("bbox", [0, 0, 0, 0]) for d in item.get("detections", []) if d.get("label") == "person"]
        frame_records.append((frame_idx, bbs))
    tracks: List[Track] = []
    next_id = 1
    # Active track centroids for previous frame
    active: List[Track] = []
    prev_centroids = None
    prev_frame = None
    for frame_idx, bbs in frame_records:
        if prev_frame is None:
            # seed new tracks
            for bb in bbs:
                tid = f"g{next_id:04d}"; next_id += 1
                tracks.append(Track(id=tid, frames=[frame_idx], bboxes=[bb]))
            prev_centroids = np.array([[(bb[0]+bb[2])/2.0, (bb[1]+bb[3])/2.0] for bb in bbs], dtype=np.float32)
            active = tracks[-len(bbs):]
            prev_frame = frame_idx
            continue
        # enforce consecutive linking only
        if frame_idx != prev_frame + 1:
            # start new tracks (no interpolation)
            for bb in bbs:
                tid = f"g{next_id:04d}"; next_id += 1
                tracks.append(Track(id=tid, frames=[frame_idx], bboxes=[bb]))
            prev_centroids = np.array([[(bb[0]+bb[2])/2.0, (bb[1]+bb[3])/2.0] for bb in bbs], dtype=np.float32)
            active = tracks[-len(bbs):]
            prev_frame = frame_idx
            continue
        new_centroids = np.array([[(bb[0]+bb[2])/2.0, (bb[1]+bb[3])/2.0] for bb in bbs], dtype=np.float32)
        if prev_centroids is None or len(prev_centroids) == 0 or len(new_centroids) == 0:
            for bb in bbs:
                tid = f"g{next_id:04d}"; next_id += 1
                tracks.append(Track(id=tid, frames=[frame_idx], bboxes=[bb]))
            prev_centroids = new_centroids
            active = tracks[-len(bbs):]
            prev_frame = frame_idx
            continue
        dmat = np.linalg.norm(prev_centroids[:, None, :] - new_centroids[None, :, :], axis=2)
        used_new = set()
        # Greedy assignment (sufficient for low object count scenarios)
        for a_idx, track in enumerate(active):
            # find nearest new centroid
            n_idx = int(np.argmin(dmat[a_idx]))
            if n_idx in used_new:
                continue
            if dmat[a_idx, n_idx] <= max_link_dist:
                track.frames.append(frame_idx)
                track.bboxes.append(bbs[n_idx])
                used_new.add(n_idx)
        # new tracks for unassigned
        for n_idx, bb in enumerate(bbs):
            if n_idx not in used_new:
                tid = f"g{next_id:04d}"; next_id += 1
                t = Track(id=tid, frames=[frame_idx], bboxes=[bb])
                tracks.append(t)
        prev_centroids = new_centroids
        # Rebuild active list (tracks that ended at this frame)
        active = [t for t in tracks if t.frames[-1] == frame_idx]
        prev_frame = frame_idx
    return tracks


def _dominant_frequency(series: np.ndarray) -> float:
    # Stabilized: require minimum length, apply window, reject implausible (>0.5 cycles/frame)
    if len(series) < MIN_STABLE_LENGTH:
        return 0.0
    x = series - np.mean(series)
    window = np.hanning(len(x))
    spec = np.fft.rfft(x * window)
    mags = np.abs(spec)
    if len(mags) <= 2:
        return 0.0
    mags[0] = 0.0
    k = int(np.argmax(mags))
    freq = float(k) / float(len(x))
    if freq > 0.5:  # unrealistic cadence proxy
        return 0.0
    return freq


def extract_gait_embeddings(detections: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    Build simple gait embeddings from person trajectories using centroid motion and bbox aspect oscillation.
    Returns a list of {track_id, length, embedding: [..], features: {...}}.
    """
    tracks = _link_tracks(detections, max_link_dist=PRIMARY_LINK_DIST)
    if not any(len(t.frames) >= MIN_TRACK_LENGTH for t in tracks):
        tracks = _link_tracks(detections, max_link_dist=SECOND_PASS_LINK_DIST)
    outputs: List[Dict[str, object]] = []
    for t in tracks:
        length = len(t.frames)
        if length < MIN_TRACK_LENGTH:
            continue
        c = t.centroids()
        v = np.linalg.norm(np.diff(c, axis=0), axis=1)
        aspects = t.aspects()
        heights = t.heights()
        height_series = 1.0 / (aspects + 1e-6)
        step_freq = _dominant_frequency(height_series)
        emb = [
            float(np.mean(v) if len(v) else 0.0),
            float(np.std(v) if len(v) else 0.0),
            float(np.mean(aspects)),
            float(np.std(aspects)),
            float(step_freq),
        ]
        mean_speed = emb[0]
        std_speed = emb[1]
        aspect_var = emb[3]
        # Quality score heuristic: combines track length proportion, speed stability, moderate aspect variance
        length_term = min(1.0, length / 120.0)
        stability_term = 1.0 - min(1.0, (std_speed / (mean_speed + 1e-6)) * 0.5) if mean_speed > 0 else 0.0
        aspect_term = 1.0 - min(1.0, aspect_var * 2.0)
        quality = max(0.0, min(1.0, 0.5 * length_term + 0.3 * stability_term + 0.2 * aspect_term))
        outputs.append(
            {
                "track_id": t.id,
                "length": length,
                "frames": t.frames,
                "bboxes": t.bboxes,
                "embedding": emb,
                "centroids": t.centroids().tolist(),
                "bbox_heights": heights.tolist(),
                "features": {
                    "mean_speed": emb[0],
                    "std_speed": emb[1],
                    "mean_aspect": emb[2],
                    "std_aspect": emb[3],
                    "step_freq": emb[4],
                    "median_height": float(np.median(heights) if len(heights) else 0.0),
                    "quality_score": float(quality),
                },
            }
        )
    return outputs
