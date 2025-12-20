from __future__ import annotations
import json
from pathlib import Path
from typing import List

from .base import EffectorAdapter


class TaskJsonlEffector(EffectorAdapter):
    """Writes task dictionaries to a JSONL file for downstream consumption."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, tasks: List[dict]) -> None:
        if not tasks:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")