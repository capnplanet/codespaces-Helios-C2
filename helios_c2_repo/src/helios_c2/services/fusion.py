from __future__ import annotations
from typing import List, Dict
from collections import defaultdict

from .base import Service, ServiceContext
from ..types import SensorReading, EntityTrack, Event


class FusionService(Service):
    name = "fusion"
    version = "0.1"

    def run(self, readings: List[SensorReading], ctx: ServiceContext) -> Dict[str, any]:
        # Simple fusion: group by domain and track_id in details
        tracks: Dict[str, EntityTrack] = {}
        domain_counts = defaultdict(int)

        for r in readings:
            domain_counts[r.domain] += 1
            track_id = r.details.get("track_id")
            if not track_id:
                track_id = f"anon_{r.domain}_{r.sensor_id}"
            if track_id not in tracks:
                tracks[track_id] = EntityTrack(
                    id=track_id,
                    domain=r.domain,
                    label=f"{r.domain}_track",
                    attributes={},
                    last_seen_ms=r.ts_ms,
                )
            else:
                tracks[track_id].last_seen_ms = max(tracks[track_id].last_seen_ms, r.ts_ms)

        # We don't generate new events here; that's the rule engine's job.
        ctx.audit.write("fusion_done", {"tracks": len(tracks), "domains": dict(domain_counts)})
        return {"readings": readings, "tracks": tracks}
