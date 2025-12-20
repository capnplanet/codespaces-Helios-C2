from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class GovernanceConfig:
    forbid_actions: List[str]


class GovernanceError(RuntimeError):
    pass


class Governance:
    def __init__(self, cfg: GovernanceConfig):
        self.cfg = cfg

    def check_action(self, action: str) -> None:
        if action in self.cfg.forbid_actions:
            raise GovernanceError(f"Action '{action}' is forbidden by policy.")
