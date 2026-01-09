from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


@dataclass
class FusedFeatures:
    """Non-identifying fused features for a track/entity.

    This is deliberately coarse and intended for demo analytics only.
    """

    gait_embedding: List[float] = field(default_factory=list)
    soft_biometrics: List[float] = field(default_factory=list)


@dataclass
class Observation:
    entity_id: str
    timestamp: float
    camera_id: str
    bbox: Optional[List[float]] = None  # normalized [x1,y1,x2,y2]
    features: FusedFeatures = field(default_factory=FusedFeatures)


@dataclass
class EntityProfile:
    entity_id: str
    track_id: Optional[str] = None
    observations: List[Observation] = field(default_factory=list)


def _hour_of_day(epoch_seconds: float) -> int:
    try:
        return int(time.localtime(epoch_seconds).tm_hour)
    except Exception:
        return 0


def _soft_biometrics_from_norm_bbox(bbox: List[float]) -> List[float]:
    # bbox normalized [x1,y1,x2,y2]
    if not bbox or len(bbox) != 4:
        return [0.0, 0.0, 0.0]
    x1, y1, x2, y2 = [float(x) for x in bbox]
    w = max(1e-6, x2 - x1)
    h = max(1e-6, y2 - y1)
    area = w * h
    aspect = h / w
    return [h, aspect, area]


def _collect_media_payload(readings: Iterable[Any]) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Find the vision video detections payload and gait embeddings payload."""

    video_payload = None
    gait_payload = None
    for r in readings:
        source_type = getattr(r, "source_type", None)
        details = getattr(r, "details", None) or {}
        if source_type == "video" and "detections" in details and video_payload is None:
            video_payload = details
        if source_type == "gait" and "gait_embeddings" in details and gait_payload is None:
            gait_payload = details
    return video_payload, gait_payload


def build_entity_profiles(
    readings: Iterable[Any],
    *,
    base_timestamp_ms: Optional[int] = None,
    assumed_fps: float = 30.0,
) -> Dict[str, Any]:
    """Build entity profiles from media-module SensorReadings.

    Works best when `gait_embeddings` are present (from `modules.gait`).
    Falls back to per-frame (untracked) observations otherwise.
    """

    video_payload, gait_payload = _collect_media_payload(readings)
    detections = (video_payload or {}).get("detections") or []
    gait_embeddings = (gait_payload or {}).get("gait_embeddings") or []

    if base_timestamp_ms is None:
        # Try to infer from first reading.
        for r in readings:
            ts = getattr(r, "ts_ms", None)
            if ts is not None:
                base_timestamp_ms = int(ts)
                break
    if base_timestamp_ms is None:
        base_timestamp_ms = int(time.time() * 1000)

    base_epoch = base_timestamp_ms / 1000.0

    profiles: Dict[str, EntityProfile] = {}

    def get_profile(track_id: Optional[str]) -> EntityProfile:
        # Stable entity IDs for repeatability within a run: map by track_id if present.
        if track_id:
            entity_id = f"ent-{track_id}"
        else:
            entity_id = f"ent-{uuid.uuid4()}"
        if entity_id not in profiles:
            profiles[entity_id] = EntityProfile(entity_id=entity_id, track_id=track_id)
        return profiles[entity_id]

    # Preferred path: use gait embeddings as the track backbone.
    if gait_embeddings:
        for emb in gait_embeddings:
            track_id = str(emb.get("track_id") or "")
            if not track_id:
                continue
            frames = [int(x) for x in (emb.get("frames") or [])]
            bboxes = emb.get("bboxes") or []
            gait_vec = [float(x) for x in (emb.get("embedding") or [])]

            prof = get_profile(track_id)
            for i, frame_idx in enumerate(frames):
                ts = base_epoch + (frame_idx / float(assumed_fps or 30.0))
                bbox = None
                if i < len(bboxes) and isinstance(bboxes[i], list) and len(bboxes[i]) == 4:
                    bbox = [float(x) for x in bboxes[i]]
                soft = _soft_biometrics_from_norm_bbox(bbox) if bbox else [0.0, 0.0, 0.0]
                prof.observations.append(
                    Observation(
                        entity_id=prof.entity_id,
                        timestamp=ts,
                        camera_id="media",
                        bbox=bbox,
                        features=FusedFeatures(gait_embedding=gait_vec, soft_biometrics=soft),
                    )
                )

    # Fallback: no tracking signal; create a lightweight per-frame pool.
    else:
        for item in detections:
            frame_idx = int(item.get("frame", 0))
            ts = base_epoch + (frame_idx / float(assumed_fps or 30.0))
            for det in item.get("detections", []) or []:
                if det.get("label") != "person":
                    continue
                bbox = det.get("bbox")
                if not isinstance(bbox, list) or len(bbox) != 4:
                    bbox = None
                soft = _soft_biometrics_from_norm_bbox(bbox) if bbox else [0.0, 0.0, 0.0]
                prof = get_profile(None)
                prof.observations.append(
                    Observation(
                        entity_id=prof.entity_id,
                        timestamp=ts,
                        camera_id="media",
                        bbox=bbox,
                        features=FusedFeatures(gait_embedding=[], soft_biometrics=soft),
                    )
                )

    # Summaries (pattern-of-life style)
    summaries: List[Dict[str, Any]] = []
    for p in profiles.values():
        if not p.observations:
            summaries.append(
                {
                    "entity_id": p.entity_id,
                    "track_id": p.track_id,
                    "num_observations": 0,
                    "cameras_histogram": {},
                    "hours_histogram": {},
                    "dominant_camera": None,
                    "dominant_hour_of_day": None,
                    "time_span_seconds": 0.0,
                }
            )
            continue
        by_cam: Dict[str, int] = {}
        by_hr: Dict[int, int] = {}
        times = np.array([o.timestamp for o in p.observations], dtype=float)
        for o in p.observations:
            by_cam[o.camera_id] = by_cam.get(o.camera_id, 0) + 1
            hr = _hour_of_day(o.timestamp)
            by_hr[hr] = by_hr.get(hr, 0) + 1
        dominant_cam = max(by_cam.items(), key=lambda kv: kv[1])[0] if by_cam else None
        dominant_hr = max(by_hr.items(), key=lambda kv: kv[1])[0] if by_hr else None
        summaries.append(
            {
                "entity_id": p.entity_id,
                "track_id": p.track_id,
                "num_observations": len(p.observations),
                "cameras_histogram": by_cam,
                "hours_histogram": {str(k): v for k, v in sorted(by_hr.items(), key=lambda kv: kv[0])},
                "dominant_camera": dominant_cam,
                "dominant_hour_of_day": dominant_hr,
                "time_span_seconds": float(times.max() - times.min()) if len(times) > 1 else 0.0,
            }
        )

    return {
        "schema_version": "0.1",
        "generated_at": time.time(),
        "entities": [asdict(p) for p in profiles.values()],
        "summaries": summaries,
        "has_gait_tracks": bool(gait_embeddings),
    }


def write_entity_profiles(readings: Iterable[Any], out_path: Path | str) -> Path:
    payload = build_entity_profiles(readings)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path
