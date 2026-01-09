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
from typing import Tuple

import yaml

from .audit import AuditLogger


class HeliosAPIHandler(SimpleHTTPRequestHandler):
    out_dir: Path
    config_path: Path
    suggestion_path: Path
    casebook_path: Path
    audit_cfg: dict

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
            return self._json_response({"ok": True, "result": result})
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

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/events":
            return self._serve_events()
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
        return self._json_response({"error": "not found"}, status=404)


def run_server(out_dir: Path, config_path: Path, ui_dir: Path, host: str, port: int) -> None:
    os.chdir(ui_dir)
    handler = HeliosAPIHandler
    handler.out_dir = out_dir
    handler.config_path = config_path
    handler.suggestion_path = out_dir / "action_suggestion.json"
    handler.casebook_path = out_dir / "casebook.json"
    try:
        cfg_raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except Exception:
        cfg_raw = {}
    handler.audit_cfg = cfg_raw.get("audit", {}) or {}
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
