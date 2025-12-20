from __future__ import annotations
from typing import List, Dict
from collections import defaultdict

from .base import Service, ServiceContext
from ..types import TaskRecommendation


class AutonomyService(Service):
    name = "autonomy"
    version = "0.1"

    def run(self, tasks: List[TaskRecommendation], ctx: ServiceContext) -> Dict[str, any]:
        # Cluster tasks by assignee_domain and priority to form a simple "plan"
        by_domain = defaultdict(list)
        for t in tasks:
            by_domain[t.assignee_domain].append(
                {"id": t.id, "event_id": t.event_id, "priority": t.priority}
            )
        plan = {"plans": dict(by_domain)}
        ctx.audit.write("autonomy_plan", {"domains": list(by_domain.keys())})
        return plan
