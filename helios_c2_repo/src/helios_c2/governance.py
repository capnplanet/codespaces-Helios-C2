from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from .types import Event, TaskRecommendation


SEVERITY_ORDER = ["info", "notice", "warning", "critical"]


@dataclass
class GovernanceConfig:
    forbid_actions: List[str] = field(default_factory=list)
    block_domains: List[str] = field(default_factory=list)
    block_categories: List[str] = field(default_factory=list)
    severity_caps: Dict[str, str] = field(default_factory=dict)  # domain -> max severity


class GovernanceError(RuntimeError):
    pass


class Governance:
    def __init__(self, cfg: GovernanceConfig):
        self.cfg = cfg

    def _severity_rank(self, sev: str) -> int:
        try:
            return SEVERITY_ORDER.index(sev)
        except ValueError:
            return len(SEVERITY_ORDER)

    def _cap_severity(self, event: Event) -> Event:
        cap = self.cfg.severity_caps.get(event.domain)
        if not cap:
            return event
        if self._severity_rank(event.severity) > self._severity_rank(cap):
            event.severity = cap
        return event

    def check_action(self, action: str) -> None:
        if action in self.cfg.forbid_actions:
            raise GovernanceError(f"Action '{action}' is forbidden by policy.")

    def filter_event(self, event: Event) -> Event | None:
        if event.domain in self.cfg.block_domains:
            return None
        if event.category in self.cfg.block_categories:
            return None
        return self._cap_severity(event)

    def filter_tasks(self, tasks: List[TaskRecommendation]) -> List[TaskRecommendation]:
        filtered: List[TaskRecommendation] = []
        for t in tasks:
            if t.assignee_domain in self.cfg.block_domains:
                continue
            self.check_action(t.action)
            filtered.append(t)
        return filtered
