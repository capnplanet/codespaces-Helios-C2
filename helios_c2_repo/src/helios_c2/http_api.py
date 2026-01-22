from __future__ import annotations
"""Lightweight HTTP API to expose Helios exports for the demo UI.

Serves:
- /api/events : events + tasks from events.json
- /api/tasks : tasks only
- /api/audit : tail of audit_log.jsonl (or path override)
- /api/metrics : raw metrics.prom text
- /api/config : YAML config contents
- Static files from --ui-dir (defaults to ui/)

Usage:
  python -m helios_c2.http_api --out out --config configs/default.yaml --ui-dir ui --host 0.0.0.0 --port 8080

This is intentionally simple and uses only the standard library.
"""

import argparse
import json
import os
import urllib.parse
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from .audit import AuditLogger
from .utils import validate_json
from jsonschema import ValidationError


class HeliosAPIHandler(SimpleHTTPRequestHandler):
    out_dir: Path
    config_path: Path
    suggestion_path: Path
    casebook_path: Path
    audit_cfg: dict
    cmds_path: Path
    intents_path: Path
    intents_jsonl_path: Path
    playbook_path: Path
    assets_path: Path
    telemetry_path: Path


    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _json_response(self, obj, status: int = 200) -> None:
        self._set_headers(status)
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def _serve_events(self) -> None:
        events_path = self.out_dir / "events.json"
        if not events_path.exists():
            self._json_response({"error": "events.json not found"}, status=404)
            return
        data = json.loads(events_path.read_text(encoding="utf-8"))
        self._json_response(data)

    def _serve_intents(self) -> None:
        intents: List[Dict[str, Any]] = []
        if self.intents_path.exists():
            try:
                data = json.loads(self.intents_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    intents.extend(data)
                elif isinstance(data, dict) and isinstance(data.get("intents"), list):
                    intents.extend(data.get("intents"))
            except Exception:
                return self._json_response({"error": "failed to parse intents"}, status=500)

        if self.intents_jsonl_path.exists():
            try:
                for line in self.intents_jsonl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if not line.strip():
                        continue
                    raw = json.loads(line)
                    if isinstance(raw, dict):
                        intents.append(raw)
            except Exception:
                return self._json_response({"error": "failed to parse intents stream"}, status=500)

        if not intents:
            return self._json_response({"intents": []})
        return self._json_response({"intents": intents})

    def _serve_playbook_actions(self) -> None:
        if not self.playbook_path.exists():
            return self._json_response({"error": "playbook_actions.json not found"}, status=404)
        try:
            data = json.loads(self.playbook_path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to parse playbook_actions"}, status=500)
        return self._json_response({"actions": data})

    def _serve_assets(self) -> None:
        if not self.assets_path.exists():
            return self._json_response({"error": "assets.json not found"}, status=404)
        try:
            data = json.loads(self.assets_path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to parse assets"}, status=500)
        payload = {"assets": data} if isinstance(data, list) else data
        return self._json_response(payload)

    def _serve_platform_commands(self) -> None:
        if not self.cmds_path.exists():
            return self._json_response({"error": "platform_commands.json not found"}, status=404)
        try:
            data = json.loads(self.cmds_path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to parse platform_commands"}, status=500)
        return self._json_response({"commands": data})

    def _serve_tasks(self) -> None:
        events_path = self.out_dir / "events.json"
        if not events_path.exists():
            self._json_response({"error": "events.json not found"}, status=404)
            return
        data = json.loads(events_path.read_text(encoding="utf-8"))
        self._json_response({"tasks": data.get("tasks", []), "pending_tasks": data.get("pending_tasks", [])})

    def _serve_audit(self, query: urllib.parse.ParseResult) -> None:
        audit_path = self.out_dir / "audit_log.jsonl"
        tail = 200
        params = urllib.parse.parse_qs(query.query)
        if "tail" in params:
            try:
                tail = max(1, min(2000, int(params["tail"][0])))
            except Exception:
                pass
        if not audit_path.exists():
            self._json_response({"error": "audit_log.jsonl not found"}, status=404)
            return
        lines = audit_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-tail:]
        entries = [json.loads(line) for line in lines if line.strip()]
        self._json_response({"audit": entries})

    def _serve_metrics(self) -> None:
        metrics_path = self.out_dir / "metrics.prom"
        if not metrics_path.exists():
            self._set_headers(404, "text/plain")
            self.wfile.write(b"metrics.prom not found\n")
            return
        self._set_headers(200, "text/plain")
        self.wfile.write(metrics_path.read_bytes())

    def _serve_config(self) -> None:
        if not self.config_path.exists():
            self._json_response({"error": "config not found"}, status=404)
            return
        text = self.config_path.read_text(encoding="utf-8")
        self._set_headers(200, "text/plain")
        self.wfile.write(text.encode("utf-8"))

    def _serve_action_suggestion(self) -> None:
        if not self.suggestion_path.exists():
            self._json_response({"error": "action_suggestion not found"}, status=404)
            return
        data = json.loads(self.suggestion_path.read_text(encoding="utf-8"))
        self._json_response(data)

    def _safe_out_path(self, rel: str) -> Path | None:
        # Prevent path traversal; only serve files under out_dir.
        rel = (rel or "").lstrip("/")
        candidate = (self.out_dir / rel).resolve()
        out_root = self.out_dir.resolve()
        if candidate == out_root or out_root not in candidate.parents:
            return None
        return candidate

    def _serve_artifact(self, query: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(query.query)
        rel = (params.get("path") or params.get("name") or [""])[0]
        path = self._safe_out_path(rel)
        if not path:
            return self._json_response({"error": "invalid path"}, status=400)
        if not path.exists() or not path.is_file():
            return self._json_response({"error": "not found"}, status=404)

        try:
            from .integrations.mime import guess_content_type

            ctype = guess_content_type(path)
        except Exception:
            ctype = "application/octet-stream"
        self._set_headers(200, ctype)
        self.wfile.write(path.read_bytes())

    def _serve_entity_profiles(self) -> None:
        path = self.out_dir / "entity_profiles.json"
        if not path.exists():
            return self._json_response({"error": "entity_profiles.json not found"}, status=404)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to parse entity_profiles.json"}, status=500)
        return self._json_response(data)

    def _serve_graph(self) -> None:
        path = self.out_dir / "graph.json"
        if not path.exists():
            # Best-effort: build from existing out/ artifacts.
            try:
                from .integrations.ontology_graph import build_ontology_graph_from_out_dir

                graph = build_ontology_graph_from_out_dir(self.out_dir)
                try:
                    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
                except Exception:
                    pass
                return self._json_response(graph)
            except Exception as exc:
                return self._json_response({"error": "graph not found", "detail": str(exc)}, status=404)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to parse graph.json"}, status=500)
        return self._json_response(data)

    def _serve_casebook(self) -> None:
        try:
            from .integrations.casebook import load_casebook

            data = load_casebook(self.casebook_path)
        except Exception as exc:
            return self._json_response({"error": "failed to load casebook", "detail": str(exc)}, status=500)
        return self._json_response(data)

    def _handle_casebook_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)
        op = str(payload.get("op") or "").strip()
        if not op:
            return self._json_response({"error": "missing op"}, status=400)

        try:
            from .integrations import casebook

            if op == "create_case":
                created = casebook.create_case(
                    self.casebook_path,
                    title=str(payload.get("title") or "Untitled"),
                    description=str(payload.get("description") or ""),
                    domain=str(payload.get("domain") or "facility"),
                    classification=str(payload.get("classification") or "CUI"),
                )
                return self._json_response({"ok": True, "case": created})
            if op == "add_evidence":
                created = casebook.add_evidence(
                    self.casebook_path,
                    kind=str(payload.get("kind") or "Evidence"),
                    description=str(payload.get("description") or ""),
                    source=str(payload.get("source") or "operator"),
                    uri=payload.get("uri"),
                    case_ids=list(payload.get("case_ids") or []),
                    tags=list(payload.get("tags") or []),
                    classification=str(payload.get("classification") or "CUI"),
                )
                return self._json_response({"ok": True, "evidence": created})
            if op == "create_hypothesis":
                created = casebook.create_hypothesis(
                    self.casebook_path,
                    title=str(payload.get("title") or "Hypothesis"),
                    description=str(payload.get("description") or ""),
                    rationale=str(payload.get("rationale") or ""),
                    case_ids=list(payload.get("case_ids") or []),
                    evidence_ids=list(payload.get("evidence_ids") or []),
                    confidence=float(payload.get("confidence") or 0.0),
                    classification=str(payload.get("classification") or "CUI"),
                )
                return self._json_response({"ok": True, "hypothesis": created})
        except Exception as exc:
            return self._json_response({"error": "casebook op failed", "detail": str(exc)}, status=500)

        return self._json_response({"error": f"unknown op: {op}"}, status=400)

    def _handle_enhance_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)
        video_path = str(payload.get("video_path") or "").strip()
        if not video_path:
            return self._json_response({"error": "missing video_path"}, status=400)
        cfg = payload.get("config") or {}
        if not isinstance(cfg, dict):
            return self._json_response({"error": "config must be an object"}, status=400)
        try:
            from .integrations.vision_enhancement import run_enhancement

            out_dir = self.out_dir / "enhancements"
            result = run_enhancement(video_path, out_dir=out_dir, config=cfg)

            # Convert artifact paths to out-relative paths + URLs so the UI can fetch them.
            out_root = self.out_dir.resolve()
            rel_paths: Dict[str, str] = {}
            urls: Dict[str, str] = {}
            for key in ("video", "montage", "metadata"):
                val = result.get(key)
                if not val:
                    continue
                try:
                    rel = str(Path(str(val)).resolve().relative_to(out_root))
                except Exception:
                    continue
                rel_paths[key] = rel
                urls[key] = "/api/artifact?path=" + urllib.parse.quote(rel)

            return self._json_response({"ok": True, "result": {**result, "artifact_paths": rel_paths, "artifact_urls": urls}})
        except Exception as exc:
            return self._json_response({"error": "enhancement failed", "detail": str(exc)}, status=500)

    def _handle_action_suggestion_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)
        decision = str(payload.get("decision", "")).lower()
        if decision not in {"approve", "deny"}:
            return self._json_response({"error": "decision must be approve or deny"}, status=400)
        actor = payload.get("actor") or self.audit_cfg.get("actor", "human")
        token = payload.get("token") or self.audit_cfg.get("sign_secret")
        rationale = payload.get("rationale") or ""
        if not self.suggestion_path.exists():
            return self._json_response({"error": "action_suggestion not found"}, status=404)
        try:
            suggestion = json.loads(self.suggestion_path.read_text(encoding="utf-8"))
        except Exception:
            return self._json_response({"error": "failed to read suggestion"}, status=500)

        suggestion["status"] = "approved" if decision == "approve" else "denied"
        suggestion["decided_at"] = time.time()
        suggestion["decided_by"] = actor
        suggestion["decision_rationale"] = rationale

        try:
            self.suggestion_path.write_text(json.dumps(suggestion, indent=2), encoding="utf-8")
        except Exception:
            return self._json_response({"error": "failed to write suggestion"}, status=500)

        # Append to audit with optional signing
        audit_logger = AuditLogger(
            self.out_dir / "audit_log.jsonl",
            actor=str(actor),
            sign_secret=str(token) if token else None,
            verify_on_start=False,
        )
        audit_logger.write("action_suggestion_decision", {"decision": decision, "rationale": rationale, "suggestion_id": suggestion.get("id")})
        return self._json_response({"ok": True, "suggestion": suggestion})

    def _handle_platform_command_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)

        text = str(payload.get("text") or "").strip()
        target = str(payload.get("target") or "").strip()
        if not text or not target:
            return self._json_response({"error": "text and target are required"}, status=400)

        cmd_id = str(payload.get("id") or f"cmd_{int(time.time() * 1000)}")
        domain = str(payload.get("domain") or "multi")
        priority_raw = payload.get("priority")
        try:
            priority = int(priority_raw) if priority_raw is not None else 3
        except Exception:
            priority = 3

        args: Dict[str, Any] = {}
        event_id = payload.get("event_id")
        if event_id:
            args["event_id"] = event_id

        route = payload.get("route") if isinstance(payload.get("route"), list) else []

        cmd: Dict[str, Any] = {
            "id": cmd_id,
            "target": target,
            "command": text,
            "args": args,
            "phase": None,
            "priority": priority,
            "status": "queued",
            "intent_id": payload.get("intent_id"),
            "playbook_action_id": payload.get("playbook_action_id"),
            "link_window_required": False,
            "metadata": {"submitted_via": "api", "text": text},
            "asset_id": payload.get("asset_id") or target,
            "domain": domain,
            "route": route,
            "link_state": payload.get("link_state"),
        }

        existing: List[Dict[str, Any]] = []
        try:
            raw = json.loads(self.cmds_path.read_text(encoding="utf-8")) if self.cmds_path.exists() else []
            existing = raw.get("commands") if isinstance(raw, dict) else raw
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

        existing.append(cmd)
        try:
            self.cmds_path.parent.mkdir(parents=True, exist_ok=True)
            self.cmds_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Best-effort queue append if configured
        try:
            cfg_raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
            queue_path = cfg_raw.get("pipeline", {}).get("platform", {}).get("queue_path")
        except Exception:
            queue_path = None
        if queue_path:
            try:
                qpath = Path(queue_path)
                qpath.parent.mkdir(parents=True, exist_ok=True)
                with qpath.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(cmd) + "\n")
            except Exception:
                pass

        try:
            audit_logger = AuditLogger(
                self.out_dir / "audit_log.jsonl",
                actor=str(self.audit_cfg.get("actor", "commander")),
                sign_secret=str(self.audit_cfg.get("sign_secret")) if self.audit_cfg.get("sign_secret") else None,
                verify_on_start=False,
            )
            audit_logger.write(
                "platform_command_enqueued",
                {
                    "id": cmd_id,
                    "target": target,
                    "domain": domain,
                    "priority": priority,
                    "via": "api",
                },
            )
        except Exception:
            pass

        return self._json_response({"command": cmd})

    def _normalize_intent_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        intent_id = str(payload.get("id") or f"intent_{now_ms}")
        return {
            "id": intent_id,
            "text": str(payload.get("text") or "").strip(),
            "domain": str(payload.get("domain") or "multi"),
            "desired_effects": list(payload.get("desired_effects") or []),
            "constraints": list(payload.get("constraints") or []),
            "timing": payload.get("timing"),
            "priority": payload.get("priority"),
            "metadata": dict(payload.get("metadata") or {}),
            "ts_ms": int(payload.get("ts_ms") or now_ms),
        }

    def _handle_intent_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)
        intent = self._normalize_intent_payload(payload)
        if not intent.get("text"):
            return self._json_response({"error": "text is required"}, status=400)

        try:
            self.intents_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.intents_jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(intent) + "\n")
        except Exception:
            return self._json_response({"error": "failed to write intent"}, status=500)

        try:
            audit_logger = AuditLogger(
                self.out_dir / "audit_log.jsonl",
                actor=str(self.audit_cfg.get("actor", "commander")),
                sign_secret=str(self.audit_cfg.get("sign_secret")) if self.audit_cfg.get("sign_secret") else None,
                verify_on_start=False,
            )
            audit_logger.write("intent_ingest_post", {"id": intent.get("id"), "domain": intent.get("domain")})
        except Exception:
            pass

        return self._json_response({"intent": intent})

    def _normalize_telemetry_reading(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        asset_id = raw.get("asset_id") or (raw.get("details") or {}).get("asset_id")
        sensor_id = raw.get("sensor_id") or (f"{asset_id}_telemetry" if asset_id else "telemetry")
        return {
            "id": str(raw.get("id") or f"telemetry_{now_ms}"),
            "sensor_id": str(sensor_id),
            "domain": str(raw.get("domain") or (raw.get("details") or {}).get("domain") or "multi"),
            "source_type": str(raw.get("source_type") or "telemetry"),
            "ts_ms": int(raw.get("ts_ms") or now_ms),
            "geo": raw.get("geo"),
            "details": dict(raw.get("details") or {}),
        }

    def _update_assets_from_telemetry(self, reading: Dict[str, Any]) -> None:
        details = reading.get("details") or {}
        asset_id = details.get("asset_id")
        asset_blob = details.get("asset") or {}
        if not asset_id and isinstance(asset_blob, dict):
            asset_id = asset_blob.get("id")
        if not asset_id:
            return

        update = dict(asset_blob or {})
        update.setdefault("id", asset_id)
        if "domain" not in update and details.get("domain"):
            update["domain"] = details.get("domain")

        existing: List[Dict[str, Any]] = []
        try:
            raw = json.loads(self.assets_path.read_text(encoding="utf-8")) if self.assets_path.exists() else []
            if isinstance(raw, list):
                existing = raw
            elif isinstance(raw, dict) and isinstance(raw.get("assets"), list):
                existing = raw.get("assets")
        except Exception:
            existing = []

        merged: List[Dict[str, Any]] = []
        found = False
        for asset in existing:
            if not isinstance(asset, dict):
                continue
            if asset.get("id") == asset_id:
                found = True
                for key, val in update.items():
                    if val is not None:
                        asset[key] = val
                meta = dict(asset.get("metadata") or {})
                meta["telemetry_ts_ms"] = reading.get("ts_ms")
                if reading.get("geo"):
                    meta["last_geo"] = reading.get("geo")
                asset["metadata"] = meta
            merged.append(asset)

        if not found:
            meta = dict(update.get("metadata") or {})
            meta["telemetry_ts_ms"] = reading.get("ts_ms")
            if reading.get("geo"):
                meta["last_geo"] = reading.get("geo")
            update["metadata"] = meta
            merged.append(update)

        try:
            self.assets_path.parent.mkdir(parents=True, exist_ok=True)
            self.assets_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _handle_telemetry_post(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._json_response({"error": "invalid json"}, status=400)

        items = payload.get("readings") if isinstance(payload, dict) else None
        if items is None:
            items = [payload] if isinstance(payload, dict) else []
        if not isinstance(items, list) or not items:
            return self._json_response({"error": "readings must be a non-empty list or object"}, status=400)

        normalized: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            reading = self._normalize_telemetry_reading(raw)
            try:
                validate_json("sensor_reading.schema.json", reading)
            except ValidationError as exc:
                return self._json_response({"error": "telemetry schema error", "detail": str(exc)}, status=400)
            normalized.append(reading)

        if not normalized:
            return self._json_response({"error": "no valid readings"}, status=400)

        try:
            self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            with self.telemetry_path.open("a", encoding="utf-8") as f:
                for reading in normalized:
                    f.write(json.dumps(reading) + "\n")
        except Exception:
            return self._json_response({"error": "failed to write telemetry"}, status=500)

        for reading in normalized:
            self._update_assets_from_telemetry(reading)

        return self._json_response({"ok": True, "count": len(normalized)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/events":
            return self._serve_events()
        if parsed.path == "/api/intents":
            return self._serve_intents()
        if parsed.path == "/api/playbook_actions":
            return self._serve_playbook_actions()
        if parsed.path == "/api/platform_commands":
            return self._serve_platform_commands()
        if parsed.path == "/api/assets":
            return self._serve_assets()
        if parsed.path == "/api/tasks":
            return self._serve_tasks()
        if parsed.path == "/api/audit":
            return self._serve_audit(parsed)
        if parsed.path == "/api/metrics":
            return self._serve_metrics()
        if parsed.path == "/api/config":
            return self._serve_config()
        if parsed.path == "/api/action_suggestion":
            return self._serve_action_suggestion()
        if parsed.path == "/api/entity_profiles":
            return self._serve_entity_profiles()
        if parsed.path == "/api/casebook":
            return self._serve_casebook()
        if parsed.path == "/api/graph":
            return self._serve_graph()
        if parsed.path == "/api/artifact":
            return self._serve_artifact(parsed)
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/action_suggestion":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_action_suggestion_post(body)
        if parsed.path == "/api/casebook":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_casebook_post(body)
        if parsed.path == "/api/enhance":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_enhance_post(body)
        if parsed.path == "/api/platform_commands":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_platform_command_post(body)
        if parsed.path == "/api/intents":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_intent_post(body)
        if parsed.path == "/api/telemetry":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            return self._handle_telemetry_post(body)
        return self._json_response({"error": "not found"}, status=404)


def run_server(out_dir: Path, config_path: Path, ui_dir: Path, host: str, port: int) -> None:
    os.chdir(ui_dir)
    handler = HeliosAPIHandler
    handler.out_dir = out_dir
    handler.config_path = config_path
    handler.suggestion_path = out_dir / "action_suggestion.json"
    handler.casebook_path = out_dir / "casebook.json"
    handler.cmds_path = out_dir / "platform_commands.json"
    handler.intents_path = out_dir / "intents.json"
    handler.intents_jsonl_path = out_dir / "intents.jsonl"
    handler.playbook_path = out_dir / "playbook_actions.json"
    handler.assets_path = out_dir / "assets.json"
    try:
        cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except Exception:
        cfg_raw = {}
    handler.audit_cfg = cfg_raw.get("audit", {}) or {}
    ingest_cfg = cfg_raw.get("pipeline", {}).get("ingest", {})
    telemetry_cfg = ingest_cfg.get("telemetry", {}) if isinstance(ingest_cfg, dict) else {}
    telemetry_path = telemetry_cfg.get("path") or ingest_cfg.get("tail", {}).get("path") or (out_dir / "telemetry.jsonl")
    handler.telemetry_path = Path(telemetry_path)
    intent_path = cfg_raw.get("pipeline", {}).get("intent", {}).get("path")
    if intent_path:
        handler.intents_jsonl_path = Path(intent_path)
    httpd = HTTPServer((host, port), handler)
    print(f"Helios API/UI server running at http://{host}:{port} serving UI from {ui_dir} and data from {out_dir}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server")
    finally:
        httpd.server_close()


def parse_args() -> Tuple[Path, Path, Path, str, int]:
    parser = argparse.ArgumentParser(description="Helios demo API/UI server")
    parser.add_argument("--out", dest="out_dir", default="out", help="Directory containing exports (events.json, metrics.prom, audit_log.jsonl)")
    parser.add_argument("--config", dest="config_path", default="configs/default.yaml", help="Pipeline config path to serve via /api/config")
    parser.add_argument("--ui-dir", dest="ui_dir", default="ui", help="Directory to serve static UI files from")
    parser.add_argument("--host", dest="host", default="0.0.0.0")
    parser.add_argument("--port", dest="port", type=int, default=8080)
    args = parser.parse_args()
    return Path(args.out_dir).resolve(), Path(args.config_path).resolve(), Path(args.ui_dir).resolve(), args.host, args.port


if __name__ == "__main__":
    out_dir, config_path, ui_dir, host, port = parse_args()
    run_server(out_dir, config_path, ui_dir, host, port)
