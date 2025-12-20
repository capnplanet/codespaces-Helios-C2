from __future__ import annotations
from typing import Any, Dict, List
import os
import yaml

from .audit import AuditLogger
from .governance import Governance, GovernanceConfig
from .rules_engine import RulesEngine, Rule
from .services.base import ServiceContext
from .services.ingest import IngestService
from .services.fusion import FusionService
from .services.decider import DecisionService
from .services.autonomy import AutonomyService
from .services.exporter import ExportService
from .types import Event, TaskRecommendation
from .utils import sha256_json


SCHEMA_VERSION = "0.1"


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_policy(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_policy(base_cfg: Dict[str, Any], policy_cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Shallow merge for governance-related keys; prioritizes policy_cfg
    out = dict(base_cfg)
    pipeline = dict(out.get("pipeline", {}))
    governance = dict(pipeline.get("governance", {}))
    governance.update(policy_cfg.get("governance", {}))
    pipeline["governance"] = governance

    human_loop = dict(pipeline.get("human_loop", {}))
    human_loop.update(policy_cfg.get("human_loop", {}))
    pipeline["human_loop"] = human_loop

    guardrails = dict(pipeline.get("guardrails", {}))
    guardrails.update(policy_cfg.get("guardrails", {}))
    pipeline["guardrails"] = guardrails

    out["pipeline"] = pipeline
    return out


def load_rules(path: str) -> RulesEngine:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    rules: List[Rule] = []
    for item in raw.get("rules", []):
        rules.append(Rule(id=item["id"], when=item["when"], then=item["then"]))
    return RulesEngine(rules)


def apply_guardrails(tasks: List[TaskRecommendation], config: Dict[str, Any]) -> tuple[List[TaskRecommendation], Dict[str, Any]]:
    guard_cfg = config.get("pipeline", {}).get("guardrails", {})
    rate_limits = guard_cfg.get("rate_limits", {})
    per_domain_limits = rate_limits.get("per_domain", {})
    total_limit = rate_limits.get("total")
    per_event_limit = rate_limits.get("per_event")

    kept: List[TaskRecommendation] = []
    dropped = {"domain": 0, "total": 0, "per_event": 0}
    domain_counts: Dict[str, int] = {}
    event_counts: Dict[str, int] = {}

    for t in tasks:
        # total guard
        if total_limit is not None and len(kept) >= int(total_limit):
            dropped["total"] += 1
            continue

        # per-domain guard
        dom_limit = per_domain_limits.get(t.assignee_domain)
        if dom_limit is not None:
            count = domain_counts.get(t.assignee_domain, 0)
            if count >= int(dom_limit):
                dropped["domain"] += 1
                continue
        # per-event guard
        if per_event_limit is not None:
            ev_count = event_counts.get(t.event_id, 0)
            if ev_count >= int(per_event_limit):
                dropped["per_event"] += 1
                continue

        kept.append(t)
        domain_counts[t.assignee_domain] = domain_counts.get(t.assignee_domain, 0) + 1
        event_counts[t.event_id] = event_counts.get(t.event_id, 0) + 1

    stats = {k: v for k, v in dropped.items() if v}
    stats["kept"] = len(kept)
    return kept, stats


def run_pipeline(config: Dict[str, Any], scenario_path: str, out_dir: str) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    audit = AuditLogger(os.path.join(out_dir, "audit_log.jsonl"))
    gov_section = config.get("pipeline", {}).get("governance", {})
    gov_cfg = GovernanceConfig(
        forbid_actions=gov_section.get("forbid_actions", []),
        block_domains=gov_section.get("block_domains", []),
        block_categories=gov_section.get("block_categories", []),
        severity_caps=gov_section.get("severity_caps", {}),
    )
    governance = Governance(gov_cfg)
    ctx = ServiceContext(config=config, audit=audit, governance=governance)

    audit.write(
        "run_start",
        {
            "schema_version": SCHEMA_VERSION,
            "config_hash": sha256_json(config),
            "scenario": scenario_path,
        },
    )

    rules_path = config.get("pipeline", {}).get("rules_config", "configs/rules.sample.yaml")
    engine = load_rules(rules_path)

    ingest = IngestService()
    fusion = FusionService()
    decider = DecisionService()
    autonomy = AutonomyService()
    exporter = ExportService()

    readings = ingest.run({"scenario_path": scenario_path}, ctx)
    fused = fusion.run(readings, ctx)
    events_raw = engine.apply(fused["readings"])
    filtered_events = []
    blocked_events = 0
    capped_events = 0
    for ev in events_raw:
        orig_sev = ev.severity
        res = governance.filter_event(ev)
        if res is None:
            blocked_events += 1
            continue
        if res.severity != orig_sev:
            capped_events += 1
        filtered_events.append(res)

    audit.write(
        "rules_done",
        {"events": len(events_raw), "events_after_governance": len(filtered_events), "blocked": blocked_events, "capped": capped_events},
    )

    tasks_raw = decider.run(filtered_events, ctx)
    tasks_after_gov = governance.filter_tasks(tasks_raw)
    if len(tasks_after_gov) != len(tasks_raw):
        audit.write("governance_tasks", {"blocked": len(tasks_raw) - len(tasks_after_gov)})

    tasks_guarded, guard_stats = apply_guardrails(tasks_after_gov, config)
    if guard_stats:
        audit.write("guardrails", guard_stats)

    pending_tasks = [t for t in tasks_guarded if t.status == "pending_approval"]
    approved_tasks = [t for t in tasks_guarded if t.status == "approved"]

    if pending_tasks:
        audit.write("human_loop_pending", {"pending": len(pending_tasks)})

    _plan = autonomy.run(approved_tasks, ctx)
    paths = exporter.run(
        {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "out_dir": out_dir},
        ctx,
    )

    audit.write(
        "run_end",
        {"events": len(filtered_events), "tasks": len(approved_tasks), "pending_tasks": len(pending_tasks)},
    )
    return {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "paths": paths}
