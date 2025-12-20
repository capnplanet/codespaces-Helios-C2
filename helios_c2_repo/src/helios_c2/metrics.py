from __future__ import annotations
import time
from contextlib import contextmanager
from typing import Dict


class Metrics:
    """Lightweight in-memory counters and timers for pipeline observability."""

    def __init__(self) -> None:
        self.counters: Dict[str, float] = {}
        self.timings: Dict[str, float] = {}

    def inc(self, name: str, value: float = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    @contextmanager
    def timer(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.timings[name] = self.timings.get(name, 0) + duration
            self.counters[f"{name}_count"] = self.counters.get(f"{name}_count", 0) + 1

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {"counters": dict(self.counters), "timings": dict(self.timings)}
