from __future__ import annotations
from typing import Dict, List, Any
import os
import datetime
import time

from .base import Service, ServiceContext
from ..types import Event, TaskRecommendation
from ..adapters.task_jsonl import TaskJsonlEffector
from ..utils import pretty_json, validate_json
from jsonschema import ValidationError


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
        stix_cfg = export_cfg.get("stix", {})
        task_jsonl_cfg = export_cfg.get("task_jsonl")

        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        obj = {
            "schema_version": ctx.config.get("helios", {}).get("schema_version", "0.1"),
            "generated_at": generated_at,
            "events": [e.__dict__ for e in events],
            "tasks": [t.__dict__ for t in tasks],
            "pending_tasks": [t.__dict__ for t in pending_tasks],
        }

        result_paths: Dict[str, str] = {}

        try:
            validate_json("events.schema.json", obj)
        except ValidationError as exc:
            ctx.audit.write("export_schema_error", {"error": str(exc)})

        if "json" in formats:
            path = os.path.join(out_dir, "events.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_json(obj))
            result_paths["json"] = path
            ctx.metrics.inc("export_json_writes")

        if "stdout" in formats:
            print(pretty_json(obj))
            result_paths["stdout"] = "stdout"

        if "webhook" in formats and webhook_cfg:
            import urllib.request

            payload = pretty_json(obj).encode("utf-8")
            retries = int(webhook_cfg.get("retries", 0))
            backoff = float(webhook_cfg.get("backoff_seconds", 1.0))
            dlq_path = webhook_cfg.get("dlq_path")
            attempt = 0
            while True:
                try:
                    req = urllib.request.Request(
                        webhook_cfg["url"],
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=int(webhook_cfg.get("timeout_seconds", 5))):
                        pass
                    result_paths["webhook"] = webhook_cfg["url"]
                    ctx.metrics.inc("export_webhook_success")
                    break
                except Exception as exc:  # pragma: no cover - network optional
                    attempt += 1
                    ctx.audit.write("export_webhook_error", {"error": str(exc), "attempt": attempt})
                    if attempt > retries:
                        if dlq_path:
                            os.makedirs(os.path.dirname(dlq_path), exist_ok=True)
                            with open(dlq_path, "ab") as f:
                                f.write(payload + b"\n")
                        ctx.metrics.inc("export_webhook_failed")
                        break
                    time.sleep(backoff)

        if "task_jsonl" in formats and task_jsonl_cfg:
            eff = TaskJsonlEffector(
                task_jsonl_cfg.get("path", os.path.join(out_dir, "tasks.jsonl")),
                rotate_max_bytes=int(task_jsonl_cfg.get("rotate_max_bytes", 0)) or None,
            )
            eff.emit([t.__dict__ for t in tasks])
            result_paths["task_jsonl"] = str(eff.path)
            ctx.metrics.inc("export_task_jsonl_writes")

        if "stix" in formats:
            from ..exporters.stix import build_stix_bundle

            bundle = build_stix_bundle(events, tasks + pending_tasks, stix_cfg)
            path = os.path.join(out_dir, "events_stix.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_json(bundle))
            result_paths["stix"] = path
            ctx.metrics.inc("export_stix_writes")

        ctx.audit.write(
            "export_done",
            {"paths": result_paths, "events": len(events), "tasks": len(tasks), "pending_tasks": len(pending_tasks)},
        )
        return result_paths
