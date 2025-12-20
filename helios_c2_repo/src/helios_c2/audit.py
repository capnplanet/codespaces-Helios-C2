from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict
import time
import orjson


@dataclass
class AuditEvent:
    ts_unix: float
    kind: str
    payload: Dict[str, Any]


class AuditLogger:
    def __init__(self, path: str):
        self.path = path

    def write(self, kind: str, payload: Dict[str, Any]) -> None:
        evt = AuditEvent(ts_unix=time.time(), kind=kind, payload=payload)
        line = orjson.dumps(asdict(evt)).decode("utf-8")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
