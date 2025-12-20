from __future__ import annotations
from typing import Dict, List, Any
import os
import datetime

from .base import Service, ServiceContext
from ..types import Event, TaskRecommendation
from ..utils import pretty_json


class ExportService(Service):
    name = "export"
    version = "0.1"

    def run(self, inp: Dict[str, Any], ctx: ServiceContext) -> Dict[str, str]:
        out_dir = inp["out_dir"]
        os.makedirs(out_dir, exist_ok=True)

        events: List[Event] = inp["events"]
        tasks: List[TaskRecommendation] = inp["tasks"]

        obj = {
            "schema_version": ctx.config.get("helios", {}).get("schema_version", "0.1"),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "events": [e.__dict__ for e in events],
            "tasks": [t.__dict__ for t in tasks],
        }

        path = os.path.join(out_dir, "events.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(pretty_json(obj))

        ctx.audit.write("export_done", {"path": path, "events": len(events), "tasks": len(tasks)})
        return {"json": path}
