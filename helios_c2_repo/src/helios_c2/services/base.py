from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict

from ..audit import AuditLogger
from ..governance import Governance
from ..metrics import Metrics


@dataclass
class ServiceContext:
    config: Dict[str, Any]
    audit: AuditLogger
    governance: Governance
    metrics: Metrics


class Service:
    name: str = "service"
    version: str = "0.1"

    def run(self, inp: Any, ctx: ServiceContext) -> Any:
        raise NotImplementedError
