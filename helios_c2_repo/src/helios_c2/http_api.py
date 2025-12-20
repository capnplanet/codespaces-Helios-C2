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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Tuple


class HeliosAPIHandler(SimpleHTTPRequestHandler):
    out_dir: Path
    config_path: Path

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
        return super().do_GET()


def run_server(out_dir: Path, config_path: Path, ui_dir: Path, host: str, port: int) -> None:
    os.chdir(ui_dir)
    handler = HeliosAPIHandler
    handler.out_dir = out_dir
    handler.config_path = config_path
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
