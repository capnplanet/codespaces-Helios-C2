from __future__ import annotations
from typing import List, Protocol

from ..types import SensorReading
from ..services.base import ServiceContext


class IngestAdapter(Protocol):
    """Protocol for ingest adapters that produce SensorReadings."""

    def collect(self, ctx: ServiceContext) -> List[SensorReading]:
        ...


class EffectorAdapter(Protocol):
    """Protocol for effector adapters that consume task dictionaries."""

    def emit(self, tasks: list[dict]) -> None:
        ...