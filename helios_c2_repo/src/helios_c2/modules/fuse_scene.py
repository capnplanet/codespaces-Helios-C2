from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from . import watchlist
from .worker.modelhub.registry import model_provenance


def _seed_from_path(media_path: Path | None) -> int:
    if media_path is None:
        return 42
    digest = sha256(str(media_path).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_scene_graph(tracks, plates, asr, sounds, actions, thermal, media_path: Path | None = None):
    seed = _seed_from_path(media_path)
    base_time = datetime.now(tz=timezone.utc).replace(microsecond=0)

    watchlist_rows = watchlist.fetch_all()
    if watchlist_rows:
        subject = watchlist_rows[seed % len(watchlist_rows)]
        person_entity = {
            "entity_id": f"person::{subject['id']}",
            "entity_type": "person",
            "attributes": {
                "name": subject["name"],
                "source": subject["source"],
            },
        }
    else:
        person_entity = {
            "entity_id": "person::demo-subject",
            "entity_type": "person",
            "attributes": {"name": "Uncatalogued Subject", "source": "demo"},
        }

    vehicle_entity = {
        "entity_id": f"vehicle::{plates[0]['plate']}" if plates else "vehicle::demo",
        "entity_type": "vehicle",
        "attributes": {"plate": plates[0]["plate"] if plates else "UN-0000"},
    }

    detections = tracks[0]["detections"] if tracks else []
    first_label = detections[0]["label"] if detections else "person"

    events = []
    events.append(
        {
            "event_id": f"evt::{seed:08x}::weapon",
            "case_id": None,
            "event_type": "weapon_presence" if first_label != "vehicle" else "convoy_formation",
            "ts": (base_time).isoformat().replace("+00:00", "Z"),
            "location": {"lat": 34.049 + (seed % 50) * 0.0001, "lon": -118.249 - (seed % 35) * 0.0001},
            "entities": [person_entity, vehicle_entity],
            "properties": {
                "detections": detections,
                "sounds": sounds,
                "transcript": " ".join(segment["text"] for segment in asr.get("segments", [])),
                "thermal": thermal,
            },
        }
    )

    events.append(
        {
            "event_id": f"evt::{seed:08x}::assembly",
            "case_id": None,
            "event_type": "group_assembly",
            "ts": (base_time + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
            "location": {"lat": 34.051 + (seed % 30) * 0.0001, "lon": -118.247 - (seed % 20) * 0.0001},
            "entities": [person_entity],
            "properties": {
                "actions": actions,
                "notes": "Deterministic demo aggregation",
            },
        }
    )

    events.append(
        {
            "event_id": f"evt::{seed:08x}::mobility",
            "case_id": None,
            "event_type": "mobility_pattern",
            "ts": (base_time + timedelta(minutes=7)).isoformat().replace("+00:00", "Z"),
            "location": {"lat": 31.771 + (seed % 17) * 0.0001, "lon": 35.217 + (seed % 27) * 0.0001},
            "entities": [vehicle_entity],
            "properties": {
                "spacing_observed": 24 + seed % 5,
                "velocity_signature": 18 + seed % 6,
            },
        }
    )

    return {
        "events": events,
        "entities": [person_entity, vehicle_entity],
        "plates": plates,
        "asr": asr,
        "sounds": sounds,
        "actions": actions,
        "thermal": thermal,
        "model_versions": model_provenance(),
        "llm_ver": "SentinelNarratorLite-0.2",
    }
