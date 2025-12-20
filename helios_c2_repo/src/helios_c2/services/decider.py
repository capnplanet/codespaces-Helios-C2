from __future__ import annotations
from typing import List

from .base import Service, ServiceContext
from ..types import Event, TaskRecommendation


class DecisionService(Service):
    name = "decision"
    version = "0.1"

    def run(self, events: List[Event], ctx: ServiceContext) -> List[TaskRecommendation]:
        tasks: List[TaskRecommendation] = []
        sev_order_cfg = ctx.config.get("severity", {})
        sev_order = {k: int(v) for k, v in sev_order_cfg.items()} or {"info": 1, "notice": 2, "warning": 3, "critical": 4}

        hl_cfg = ctx.config.get("pipeline", {}).get("human_loop", {})
        default_require = bool(hl_cfg.get("default_require_approval", True))
        domain_require = set(hl_cfg.get("domain_require_approval", []))
        auto_approve = bool(hl_cfg.get("auto_approve", True))
        approver = hl_cfg.get("approver", "auto")

        for ev in events:
            if ev.status != "open":
                continue
            # Priority: invert severity number so higher severity -> lower priority value (1 is highest)
            sev_val = sev_order.get(ev.severity, 0)
            priority = max(1, 5 - sev_val)
            # Map domain to domain that should respond
            assignee = ev.domain if ev.domain != "multi" else "land"
            action = "investigate"
            rationale = f"{ev.summary} (severity={ev.severity}, domain={ev.domain})"
            confidence = 0.8 if ev.severity in ("warning", "critical") else 0.6

            requires_approval = assignee in domain_require or default_require
            status = "approved"
            approved_by = approver if requires_approval and auto_approve else None
            if requires_approval and not auto_approve:
                status = "pending_approval"
                approved_by = None

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
                requires_approval=requires_approval,
                status=status,
                approved_by=approved_by,
            )
            tasks.append(task)

        ctx.audit.write("decision_done", {"tasks": len(tasks)})
        return tasks
