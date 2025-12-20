from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any
import time


class InfrastructureEffector:
    """Simulates defensive infrastructure actions by appending JSONL lines."""

    def __init__(self, path: str, rotate_max_bytes: int | None = None):
        self.path = Path(path)
        self.rotate_max_bytes = rotate_max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)

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
