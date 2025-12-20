from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

from .types import SensorReading, Event
from .utils import sha256_json


@dataclass
class Rule:
    id: str
    when: Dict[str, Any]
    then: Dict[str, Any]


class RulesEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = rules

    def apply(self, readings: List[SensorReading]) -> List[Event]:
        events: List[Event] = []
        for r in readings:
            for rule in self.rules:
                if self._matches(rule, r):
                    ev = self._make_event(rule, r)
                    events.append(ev)
        return events

    def _matches(self, rule: Rule, reading: SensorReading) -> bool:
        cond = rule.when
        if cond.get("domain") and cond["domain"] != reading.domain:
            return False
        if cond.get("source_type") and cond["source_type"] != reading.source_type:
            return False
        condition = cond.get("condition")
        threshold = cond.get("threshold")
        # Minimal, scenario-specific logic:
        if condition == "altitude_below":
            alt = reading.details.get("altitude_ft", 0)
            return alt < float(threshold)
        if condition == "night_motion":
            return bool(reading.details.get("night_motion", False))
        if condition == "port_scan":
            count = reading.details.get("scan_count", 0)
            return count >= int(threshold)
        if condition == "keyword":
            text = str(reading.details.get("text", "")).lower()
            return str(threshold).lower() in text
        if condition == "detail_equals":
            field = cond.get("field")
            return reading.details.get(field) == threshold if field else False
        if condition == "detail_flag":
            field = cond.get("field")
            return bool(reading.details.get(field, False)) if field else False
        return False

    def _make_event(self, rule: Rule, reading: SensorReading) -> Event:
        then = rule.then
        evidence_hash = sha256_json(reading.details or {})
        evidence = [
            {
                "type": "sensor_reading",
                "id": reading.id,
                "source": reading.sensor_id,
                "hash": evidence_hash,
                "observables": reading.details,
            }
        ]
        return Event(
            id=f"ev_{reading.id}_{rule.id}",
            category=then.get("category", "status"),
            severity=then.get("severity", "info"),
            status="open",
            domain=reading.domain,
            summary=then.get("summary", "rule_triggered"),
            time_window={"start_ms": reading.ts_ms, "end_ms": reading.ts_ms},
            entities=[reading.details.get("track_id", "unknown")],
            sources=[reading.sensor_id],
            tags=[rule.id],
            evidence=evidence,
        )
