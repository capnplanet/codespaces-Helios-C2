from __future__ import annotations
from typing import List

from .base import Service, ServiceContext
from ..types import Event, TaskRecommendation


class DecisionService(Service):
    name = "decision"
    version = "0.1"

    def run(self, events: List[Event], ctx: ServiceContext) -> List[TaskRecommendation]:
        tasks: List[TaskRecommendation] = []
        sev_order = {"info": 4, "notice": 3, "warning": 2, "critical": 1}

        for ev in events:
            if ev.status != "open":
                continue
            # Simple priority rule: severity -> priority
            priority = sev_order.get(ev.severity, 4)
            # Map domain to domain that should respond
            assignee = ev.domain if ev.domain != "multi" else "land"
            action = "investigate"
            rationale = f"{ev.summary} (severity={ev.severity}, domain={ev.domain})"
            confidence = 0.8 if ev.severity in ("warning", "critical") else 0.6

            # Governance guard (forbidden actions)
            ctx.governance.check_action(action)

            task = TaskRecommendation(
                id=f"task_{ev.id}",
                event_id=ev.id,
                action=action,
                assignee_domain=assignee,
                priority=priority,
                rationale=rationale,
                confidence=confidence,
            )
            tasks.append(task)

        ctx.audit.write("decision_done", {"tasks": len(tasks)})
        return tasks
