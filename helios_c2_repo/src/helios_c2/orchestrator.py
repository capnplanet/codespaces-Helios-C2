from __future__ import annotations
from typing import Any, Dict, List
import os
import yaml
from fnmatch import fnmatch

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
from .risk_store import RiskStore
from .adapters.file_tail import FileTailAdapter
from .adapters.media_modules import collect_media_readings
from .metrics import Metrics
import time


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


def apply_guardrails(tasks: List[TaskRecommendation], config: Dict[str, Any], metrics: Metrics | None = None) -> tuple[List[TaskRecommendation], Dict[str, Any]]:
    guard_cfg = config.get("pipeline", {}).get("guardrails", {})
    rate_limits = guard_cfg.get("rate_limits", {})
    per_domain_limits = rate_limits.get("per_domain", {})
    total_limit = rate_limits.get("total")
    per_event_limit = rate_limits.get("per_event")
    per_asset_limits = rate_limits.get("per_asset_infra", {})
    per_asset_patterns = rate_limits.get("per_asset_infra_patterns", [])

    kept: List[TaskRecommendation] = []
    dropped = {"domain": 0, "total": 0, "per_event": 0, "per_asset_infra": 0, "per_asset_infra_pattern": 0}
    domain_counts: Dict[str, int] = {}
    event_counts: Dict[str, int] = {}
    asset_counts: Dict[str, int] = {}
    asset_pattern_counts: Dict[str, int] = {}

    for t in tasks:
        # total guard
        if total_limit is not None and len(kept) >= int(total_limit):
            dropped["total"] += 1
            if metrics:
                metrics.inc("guardrail_drop_total")
            continue

        # per-domain guard
        dom_limit = per_domain_limits.get(t.assignee_domain)
        if dom_limit is not None:
            count = domain_counts.get(t.assignee_domain, 0)
            if count >= int(dom_limit):
                dropped["domain"] += 1
                if metrics:
                    metrics.inc("guardrail_drop_domain")
                continue
        # per-event guard
        if per_event_limit is not None:
            ev_count = event_counts.get(t.event_id, 0)
            if ev_count >= int(per_event_limit):
                dropped["per_event"] += 1
                if metrics:
                    metrics.inc("guardrail_drop_per_event")
                continue

        asset_id = getattr(t, "asset_id", None)
        matched_pattern = None
        if asset_id:
            if asset_id in per_asset_limits:
                a_limit = per_asset_limits.get(asset_id)
                a_count = asset_counts.get(asset_id, 0)
                if a_limit is not None and a_count >= int(a_limit):
                    dropped["per_asset_infra"] += 1
                    if metrics:
                        metrics.inc("guardrail_drop_per_asset")
                    continue

            for pattern_cfg in per_asset_patterns:
                pat = pattern_cfg.get("pattern")
                limit = pattern_cfg.get("limit")
                if not pat or limit is None:
                    continue
                if fnmatch(asset_id, pat):
                    matched_pattern = pat
                    p_count = asset_pattern_counts.get(pat, 0)
                    if p_count >= int(limit):
                        dropped["per_asset_infra_pattern"] += 1
                        if metrics:
                            metrics.inc("guardrail_drop_per_asset_pattern")
                        matched_pattern = None
                        break
                    break

        kept.append(t)
        domain_counts[t.assignee_domain] = domain_counts.get(t.assignee_domain, 0) + 1
        event_counts[t.event_id] = event_counts.get(t.event_id, 0) + 1
        if asset_id:
            asset_counts[asset_id] = asset_counts.get(asset_id, 0) + 1
        if matched_pattern:
            asset_pattern_counts[matched_pattern] = asset_pattern_counts.get(matched_pattern, 0) + 1

    stats = {k: v for k, v in dropped.items() if v}
    stats["kept"] = len(kept)
    return kept, stats


def evaluate_guardrail_health(guard_stats: Dict[str, Any], alert_threshold: float) -> Dict[str, Any]:
    dropped_total = (
        guard_stats.get("domain", 0)
        + guard_stats.get("total", 0)
        + guard_stats.get("per_event", 0)
        + guard_stats.get("per_asset_infra", 0)
        + guard_stats.get("per_asset_infra_pattern", 0)
    )
    kept = guard_stats.get("kept", 0)
    total = kept + dropped_total
    if total == 0:
        return {}
    ratio = dropped_total / total
    if ratio >= alert_threshold:
        return {"dropped_total": dropped_total, "kept": kept, "drop_ratio": ratio}
    return {}


def apply_risk_budget(tasks: List[TaskRecommendation], events_by_id: Dict[str, Event], config: Dict[str, Any]) -> tuple[List[TaskRecommendation], Dict[str, Any]]:
    guard_cfg = config.get("pipeline", {}).get("guardrails", {})
    budgets = guard_cfg.get("risk_budgets", {})
    base_backoff = guard_cfg.get("risk_backoff_base_sec", 10)
    window = guard_cfg.get("risk_window_sec", 300)
    store_path = guard_cfg.get("risk_store_path")
    now = time.time()
    counts: Dict[str, int] = {}
    held = 0
    result: List[TaskRecommendation] = []
    store: RiskStore | None = None
    if store_path:
        store = RiskStore(store_path, window_seconds=window)

    for t in tasks:
        ev = events_by_id.get(t.event_id)
        severity = ev.severity if ev else "info"
        tenant = t.tenant
        limit = budgets.get(tenant, {}).get("critical_limit")
        if severity == "critical" and limit is not None:
            current = store.increment_and_get(tenant, now) if store else counts.get(tenant, 0) + 1
            counts[tenant] = current
            if current > int(limit):
                held += 1
                backoff = base_backoff * (2 ** max(0, current - limit))
                t.status = "risk_hold"
                t.hold_reason = "risk_budget_exceeded"
                t.hold_until_epoch = now + backoff
        result.append(t)

    stats = {"held": held, "counts": counts}
    if store_path:
        stats["store_path"] = store_path
    return result, stats


def run_pipeline(config: Dict[str, Any], scenario_path: str, out_dir: str) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    audit_cfg = config.get("audit", {})
    audit_actor = audit_cfg.get("actor", "system")
    audit_secret = audit_cfg.get("sign_secret")
    audit = AuditLogger(
        os.path.join(out_dir, "audit_log.jsonl"),
        actor=audit_actor,
        sign_secret=audit_secret,
        verify_on_start=bool(audit_cfg.get("verify_on_start", False)),
        require_signing=bool(audit_cfg.get("require_signing", False)),
    )
    gov_section = config.get("pipeline", {}).get("governance", {})
    gov_cfg = GovernanceConfig(
        forbid_actions=gov_section.get("forbid_actions", []),
        block_domains=gov_section.get("block_domains", []),
        block_categories=gov_section.get("block_categories", []),
        severity_caps=gov_section.get("severity_caps", {}),
    )
    governance = Governance(gov_cfg)
    guardrails_cfg = config.setdefault("pipeline", {}).setdefault("guardrails", {})
    store_path = guardrails_cfg.get("risk_store_path")
    if store_path and not os.path.isabs(store_path):
        guardrails_cfg["risk_store_path"] = os.path.join(out_dir, store_path)
    metrics = Metrics()
    ctx = ServiceContext(config=config, audit=audit, governance=governance, metrics=metrics)

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

    ingest_mode = config.get("pipeline", {}).get("ingest", {}).get("mode", "scenario")
    with metrics.timer("ingest"):
        if ingest_mode == "tail":
            tail_cfg = config.get("pipeline", {}).get("ingest", {}).get("tail", {})
            adapter = FileTailAdapter(
                path=tail_cfg.get("path", scenario_path),
                max_items=int(tail_cfg.get("max_items", 100)),
                poll_interval=float(tail_cfg.get("poll_interval_sec", 0.05)),
            )
            readings = adapter.collect(ctx)
        elif ingest_mode == "modules_media":
            ingest_cfg = config.get("pipeline", {}).get("ingest", {})
            media_cfg = ingest_cfg.get("media", {})
            modules_cfg = ingest_cfg.get("modules", {})
            media_path = media_cfg.get("path", scenario_path)
            stride = int(media_cfg.get("stride", 8))
            readings, mod_stats = collect_media_readings(media_path, stride=stride, modules_cfg=modules_cfg)
            ctx.audit.write("ingest_modules_done", {"path": media_path, "stride": stride, "stats": mod_stats})
        else:
            readings = ingest.run({"scenario_path": scenario_path}, ctx)
    with metrics.timer("fusion"):
        fused = fusion.run(readings, ctx)
    with metrics.timer("rules"):
        events_raw = engine.apply(fused["readings"])
    metrics.inc("events_raw", len(events_raw))
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

    with metrics.timer("decision"):
        tasks_raw = decider.run(filtered_events, ctx)
    tasks_after_gov = governance.filter_tasks(tasks_raw)
    if len(tasks_after_gov) != len(tasks_raw):
        audit.write("governance_tasks", {"blocked": len(tasks_raw) - len(tasks_after_gov)})

    with metrics.timer("guardrails"):
        tasks_guarded, guard_stats = apply_guardrails(tasks_after_gov, config, metrics)
    if guard_stats:
        audit.write("guardrails", guard_stats)
        health_alert = evaluate_guardrail_health(guard_stats, config.get("pipeline", {}).get("guardrails", {}).get("health_alert_drop_ratio", 0.5))
        if health_alert:
            audit.write("guardrail_health_alert", health_alert)

    events_by_id = {ev.id: ev for ev in filtered_events}
    with metrics.timer("risk_budget"):
        tasks_budgeted, budget_stats = apply_risk_budget(tasks_guarded, events_by_id, config)
    if budget_stats.get("held"):
        audit.write("risk_budget", budget_stats)

    pending_tasks = [t for t in tasks_budgeted if t.status in ("pending_approval", "risk_hold")]
    approved_tasks = [t for t in tasks_budgeted if t.status == "approved"]

    if pending_tasks:
        audit.write("human_loop_pending", {"pending": len(pending_tasks)})

    with metrics.timer("autonomy"):
        _plan = autonomy.run(approved_tasks, ctx)
    with metrics.timer("export"):
        paths = exporter.run(
            {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "out_dir": out_dir},
            ctx,
        )

    audit.write(
        "run_end",
        {
            "events": len(filtered_events),
            "tasks": len(approved_tasks),
            "pending_tasks": len(pending_tasks),
            "metrics": metrics.snapshot(),
        },
    )
    return {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "paths": paths, "metrics": metrics.snapshot()}
