from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Dict, Any


def _send_http(actions: List[Dict[str, Any]], http_cfg: Dict[str, Any]) -> bool:
    import urllib.request

    payload = json.dumps(actions).encode("utf-8")
    retries = int(http_cfg.get("retries", 0))
    backoff = float(http_cfg.get("backoff_seconds", 1.0))
    url = http_cfg.get("url")
    if not url:
        return False

    attempt = 0
    while True:
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=int(http_cfg.get("timeout_seconds", 5))):
                return True
        except Exception:
            attempt += 1
            if attempt > retries:
                break
            time.sleep(backoff)
    return False


class InfrastructureEffector:
    """Simulates defensive infrastructure actions by appending JSONL lines."""

    def __init__(self, path: str, rotate_max_bytes: int | None = None, http_config: Dict[str, Any] | None = None, dlq_path: str | None = None, metrics=None):
        self.path = Path(path)
        self.rotate_max_bytes = rotate_max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.http_config = http_config or {}
        self.dlq_path = Path(dlq_path) if dlq_path else None
        self.metrics = metrics

    def _maybe_rotate(self) -> None:
        if not self.rotate_max_bytes:
            return
        if self.path.exists() and self.path.stat().st_size >= self.rotate_max_bytes:
            ts = int(time.time())
            rotated = self.path.with_name(f"{self.path.stem}.{ts}{self.path.suffix}")
            self.path.rename(rotated)

    def emit(self, actions: List[Dict[str, Any]]) -> None:
        if not actions:
            return
        self._maybe_rotate()
        with self.path.open("a", encoding="utf-8") as f:
            for action in actions:
                f.write(json.dumps(action, ensure_ascii=False) + "\n")
        if self.metrics:
            self.metrics.inc("infra_file_writes")
            self.metrics.inc("infra_actions_written", len(actions))

        if self.http_config:
            ok = _send_http(actions, self.http_config)
            if ok:
                if self.metrics:
                    self.metrics.inc("infra_http_success")
            else:
                if self.metrics:
                    self.metrics.inc("infra_http_failed")
                if self.dlq_path:
                    self.dlq_path.parent.mkdir(parents=True, exist_ok=True)
                    with self.dlq_path.open("ab") as f:
                        f.write(json.dumps(actions).encode("utf-8") + b"\n")
