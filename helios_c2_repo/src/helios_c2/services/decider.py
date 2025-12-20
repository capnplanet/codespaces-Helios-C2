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
        min_approvals = int(rbac_cfg.get("min_approvals", 0))

        infra_cfg = ctx.config.get("pipeline", {}).get("infrastructure", {})
        infra_mappings = infra_cfg.get("mappings", [])

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

                approvals_met = len(signer_ids) >= min_approvals and (not required_roles or required_roles.issubset(satisfied_roles))

                if approvals_met and auto_approve:
                    approved_by = ",".join(signer_ids)
                elif not approvals_met and allow_unsigned and min_approvals == 0 and (not required_roles or required_roles.issubset(satisfied_roles)):
                    approved_by = approver
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

            # Infrastructure-specific mappings
            for mapping in infra_mappings:
                match = mapping.get("match", {})
                if match.get("category") and match["category"] != ev.category:
                    continue
                if match.get("domain") and match["domain"] != ev.domain:
                    continue
                for tcfg in mapping.get("tasks", []):
                    m_action = tcfg.get("action")
                    if not m_action:
                        continue
                    m_asset = tcfg.get("asset_id")
                    m_type = tcfg.get("infrastructure_type")
                    m_assignee = tcfg.get("assignee_domain", assignee)
                    m_priority = int(tcfg.get("priority", priority))
                    m_rationale = tcfg.get("rationale", rationale)
                    m_requires = tcfg.get("requires_approval")

                    requires_mapping = requires_approval
                    if m_requires is not None:
                        requires_mapping = bool(m_requires)

                    m_status = "approved"
                    m_approved_by = None

                    if requires_mapping:
                        m_signers = []
                        m_satisfied_roles = set()
                        required_roles = set(required_roles_by_domain.get(m_assignee, []))
                        message = f"{ev.id}:{m_assignee}:{m_action}:{tenant_id}"
                        for active in active_approvers:
                            aid = active.get("id")
                            token = active.get("token")
                            secret = approver_secrets.get(aid)
                            roles = approver_roles.get(aid, set())
                            if not secret or not token:
                                continue
                            if verify_hmac_token(message, token, secret):
                                m_signers.append(aid)
                                m_satisfied_roles |= roles & required_roles

                        approvals_met = len(m_signers) >= min_approvals and (not required_roles or required_roles.issubset(m_satisfied_roles))
                        if approvals_met and auto_approve:
                            m_approved_by = ",".join(m_signers)
                        elif not approvals_met and allow_unsigned and min_approvals == 0 and (not required_roles or required_roles.issubset(m_satisfied_roles)):
                            m_approved_by = approver
                        else:
                            m_status = "pending_approval"
                            m_approved_by = None

                    ctx.governance.check_action(m_action)

                    infra_task = TaskRecommendation(
                        id=f"task_{ev.id}_{m_action}_{m_asset}",
                        event_id=ev.id,
                        action=m_action,
                        infrastructure_type=m_type,
                        asset_id=m_asset,
                        assignee_domain=m_assignee,
                        priority=m_priority,
                        rationale=m_rationale,
                        confidence=confidence,
                        requires_approval=requires_mapping,
                        status=m_status,
                        approved_by=m_approved_by,
                        evidence=evidence,
                        tenant=tenant_id,
                    )
                    tasks.append(infra_task)

        ctx.audit.write("decision_done", {"tasks": len(tasks)})
        return tasks
