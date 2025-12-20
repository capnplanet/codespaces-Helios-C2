from __future__ import annotations
from typing import Any, Dict, List
import yaml

from .base import Service, ServiceContext
from ..types import SensorReading


class IngestService(Service):
    name = "ingest"
    version = "0.1"

    def run(self, inp: Dict[str, Any], ctx: ServiceContext) -> List[SensorReading]:
        scenario_path = inp["scenario_path"]
        with open(scenario_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        readings: List[SensorReading] = []
        for item in raw.get("sensor_readings", []):
            readings.append(
                SensorReading(
                    id=str(item["id"]),
                    sensor_id=str(item["sensor_id"]),
                    domain=str(item["domain"]),
                    source_type=str(item["source_type"]),
                    ts_ms=int(item["ts_ms"]),
                    geo=item.get("geo"),
                    details=item.get("details", {}),
                )
            )
        ctx.audit.write("ingest_done", {"count": len(readings), "scenario": scenario_path})
        return readings
