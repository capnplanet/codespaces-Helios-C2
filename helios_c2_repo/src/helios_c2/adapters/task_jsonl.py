from __future__ import annotations
import json
from pathlib import Path
from typing import List
import time

from .base import EffectorAdapter


class TaskJsonlEffector(EffectorAdapter):
    """Writes task dictionaries to a JSONL file for downstream consumption."""

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

    def emit(self, tasks: List[dict]) -> None:
        if not tasks:
            return
        self._maybe_rotate()
        with self.path.open("a", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")