from __future__ import annotations
from typing import List

from .base import Service, ServiceContext
from ..types import Event, TaskRecommendation
from ..utils import verify_hmac_token


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
        allow_unsigned = bool(hl_cfg.get("allow_unsigned_auto_approve", True))

        rbac_cfg = ctx.config.get("pipeline", {}).get("rbac", {})
        active_approvers = rbac_cfg.get("active_approvers", []) or ([rbac_cfg.get("active_approver", {})] if rbac_cfg.get("active_approver") else [])
        approver_secrets = {c.get("id"): c.get("secret") for c in rbac_cfg.get("approvers", [])}
        approver_roles = {c.get("id"): set(c.get("roles", [])) for c in rbac_cfg.get("approvers", [])}
        required_roles_by_domain = rbac_cfg.get("required_roles", {})

        tenant_id = ctx.config.get("tenant", {}).get("id", "default")

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
            approved_by = None
            required_roles = set(required_roles_by_domain.get(assignee, []))
            satisfied_roles = set()
            signer_ids = []
            message = f"{ev.id}:{assignee}:{action}:{tenant_id}"

            if requires_approval:
                for active in active_approvers:
                    aid = active.get("id")
                    token = active.get("token")
                    secret = approver_secrets.get(aid)
                    roles = approver_roles.get(aid, set())
                    if not secret or not token:
                        continue
                    if verify_hmac_token(message, token, secret):
                        signer_ids.append(aid)
                        satisfied_roles |= roles & required_roles
                if required_roles and not required_roles.issubset(satisfied_roles):
                    status = "pending_approval"
                    approved_by = None
                elif auto_approve and (signer_ids or allow_unsigned):
                    approved_by = ",".join(signer_ids) if signer_ids else approver
                else:
                    status = "pending_approval"
                    approved_by = None

            evidence = [
                {"type": "event_ref", "id": ev.id},
                {"type": "domain", "value": ev.domain},
            ]

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
                evidence=evidence,
                tenant=tenant_id,
            )
            tasks.append(task)

        ctx.audit.write("decision_done", {"tasks": len(tasks)})
        return tasks
