from __future__ import annotations
from typing import Any, Dict, List
import yaml
from pathlib import Path

from .base import Service, ServiceContext
from ..types import SensorReading


class IngestService(Service):
    name = "ingest"
    version = "0.1"

    def _resolve_scenario_path(self, scenario_path: str) -> Path:
        p = Path(scenario_path)
        if p.is_absolute() or p.exists():
            return p

        project_root = Path(__file__).resolve().parents[3]
        candidate = project_root / p
        if candidate.exists():
            return candidate

        return p

    def run(self, inp: Dict[str, Any], ctx: ServiceContext) -> List[SensorReading]:
        scenario_path = inp["scenario_path"]
        resolved = self._resolve_scenario_path(scenario_path)
        with open(resolved, "r", encoding="utf-8") as f:
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
        ctx.audit.write("ingest_done", {"count": len(readings), "scenario": str(resolved)})
        return readings
