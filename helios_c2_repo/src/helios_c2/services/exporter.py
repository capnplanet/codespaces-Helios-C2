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
        pending_tasks: List[TaskRecommendation] = inp.get("pending_tasks", [])

        export_cfg = ctx.config.get("pipeline", {}).get("export", {})
        formats = export_cfg.get("formats", ["json"])
        webhook_cfg = export_cfg.get("webhook")

        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        obj = {
            "schema_version": ctx.config.get("helios", {}).get("schema_version", "0.1"),
            "generated_at": generated_at,
            "events": [e.__dict__ for e in events],
            "tasks": [t.__dict__ for t in tasks],
            "pending_tasks": [t.__dict__ for t in pending_tasks],
        }

        result_paths: Dict[str, str] = {}

        if "json" in formats:
            path = os.path.join(out_dir, "events.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_json(obj))
            result_paths["json"] = path

        if "stdout" in formats:
            print(pretty_json(obj))
            result_paths["stdout"] = "stdout"

        if "webhook" in formats and webhook_cfg:
            import urllib.request

            try:
                req = urllib.request.Request(
                    webhook_cfg["url"],
                    data=pretty_json(obj).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=int(webhook_cfg.get("timeout_seconds", 5))):
                    pass
                result_paths["webhook"] = webhook_cfg["url"]
            except Exception as exc:  # pragma: no cover - network optional
                ctx.audit.write("export_webhook_error", {"error": str(exc)})

        ctx.audit.write(
            "export_done",
            {"paths": result_paths, "events": len(events), "tasks": len(tasks), "pending_tasks": len(pending_tasks)},
        )
        return result_paths
