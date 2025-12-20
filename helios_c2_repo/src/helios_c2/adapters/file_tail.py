from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List

from .base import IngestAdapter
from ..types import SensorReading
from ..services.base import ServiceContext


class FileTailAdapter(IngestAdapter):
    """Polls a file for newline-delimited JSON sensor readings."""

    def __init__(self, path: str, max_items: int = 100, poll_interval: float = 0.1):
        self.path = Path(path)
        self.max_items = max_items
        self.poll_interval = poll_interval

    def collect(self, ctx: ServiceContext) -> List[SensorReading]:
        items: List[SensorReading] = []
        if not self.path.exists():
            return items

        # Read all lines once; in a real tail we would maintain offsets.
        with self.path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            if len(items) >= self.max_items:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                items.append(
                    SensorReading(
                        id=str(obj["id"]),
                        sensor_id=str(obj["sensor_id"]),
                        domain=str(obj["domain"]),
                        source_type=str(obj["source_type"]),
                        ts_ms=int(obj["ts_ms"]),
                        geo=obj.get("geo"),
                        details=obj.get("details", {}),
                    )
                )
            except Exception as exc:  # pragma: no cover - malformed line ignored
                ctx.audit.write("ingest_tail_error", {"error": str(exc)})

        # Simulate tail polling delay for symmetry with future streaming use
        time.sleep(self.poll_interval)
        ctx.audit.write("ingest_tail", {"path": str(self.path), "count": len(items)})
        return items