from __future__ import annotations
from typing import Any, Dict, List, Optional
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
from .services.intent import IntentIngestService
from .services.playbook import PlaybookMapper
from .types import Asset, Event, TaskRecommendation, PlatformCommand, LinkState
from .utils import sha256_json
from .risk_store import RiskStore
from .adapters.file_tail import FileTailAdapter
from .adapters.media_modules import collect_media_readings
from .adapters.platform_link import PlatformCommandQueue
from .metrics import Metrics
import time
import json
from pathlib import Path


SCHEMA_VERSION = "0.1"


def _resolve_repo_relative_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p

    # Resolve relative paths against the project root so tests and CLI
    # behave consistently regardless of current working directory.
    project_root = Path(__file__).resolve().parents[2]
    candidate = project_root / p
    if candidate.exists():
        return candidate

    return p


def load_config(path: str) -> Dict[str, Any]:
    resolved = _resolve_repo_relative_path(path)
    with open(resolved, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_policy(path: str) -> Dict[str, Any]:
    resolved = _resolve_repo_relative_path(path)
    with open(resolved, "r", encoding="utf-8") as f:
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
    resolved = _resolve_repo_relative_path(path)
    with open(resolved, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    rules: List[Rule] = []
    for item in raw.get("rules", []):
        rules.append(Rule(id=item["id"], when=item["when"], then=item["then"]))
    return RulesEngine(rules)


def _link_state_to_dict(link: LinkState | None) -> Optional[Dict[str, Any]]:
    if not link:
        return None
    return {
        "target": link.target,
        "available": link.available,
        "last_check_epoch": link.last_check_epoch,
        "window_ends_epoch": link.window_ends_epoch,
        "notes": link.notes,
        "metrics": link.metrics,
    }


def _load_link_states(platform_cfg: Dict[str, Any]) -> Dict[str, LinkState]:
    link_states_cfg = platform_cfg.get("link_states", [])
    link_states: Dict[str, LinkState] = {}
    now_epoch = time.time()
    for lcfg in link_states_cfg:
        target = str(lcfg.get("target", "unknown"))
        link_states[target] = LinkState(
            target=target,
            available=bool(lcfg.get("available", True)),
            last_check_epoch=float(lcfg.get("last_check_epoch", now_epoch)),
            window_ends_epoch=lcfg.get("window_ends_epoch"),
            notes=lcfg.get("notes"),
            metrics=dict(lcfg.get("metrics") or {}),
        )
    return link_states


def _load_assets(
    platform_cfg: Dict[str, Any],
    tasks: List[TaskRecommendation],
    playbook_actions: List[Any],
    link_states: Dict[str, LinkState],
) -> List[Asset]:
    assets: List[Asset] = []
    seen: Dict[str, Asset] = {}

    def _attach_link(asset: Asset) -> Asset:
        link = link_states.get(asset.id)
        if link:
            asset.link_state = _link_state_to_dict(link)
            if link.metrics and not asset.comm_link.get("metrics"):
                asset.comm_link["metrics"] = link.metrics
        return asset

    def _add(asset: Asset) -> None:
        existing = seen.get(asset.id)
        asset = _attach_link(asset)
        if existing:
            if asset.link_state and not existing.link_state:
                existing.link_state = asset.link_state
            if asset.route and not existing.route:
                existing.route = asset.route
            if asset.comm_link and not existing.comm_link:
                existing.comm_link = asset.comm_link
            if asset.status != "available" and existing.status == "available":
                existing.status = asset.status
            return
        seen[asset.id] = asset
        assets.append(asset)

    for idx, raw in enumerate(platform_cfg.get("assets", [])):
        if not isinstance(raw, dict):
            continue
        raw_link = raw.get("link_state")
        asset = Asset(
            id=str(raw.get("id") or f"asset_{idx}"),
            domain=str(raw.get("domain") or "multi"),
            vehicle_type=raw.get("vehicle_type"),
            platform_id=raw.get("platform_id"),
            label=raw.get("label"),
            status=str(raw.get("status", "available")),
            home_wp=raw.get("home_wp"),
            loiter_alt_m=raw.get("loiter_alt_m"),
            battery_pct=raw.get("battery_pct"),
            comm_link=dict(raw.get("comm_link") or {}),
            route=list(raw.get("route") or []),
            link_state=_link_state_to_dict(raw_link) if isinstance(raw_link, LinkState) else (raw_link if isinstance(raw_link, dict) else None),
            metadata=dict(raw.get("metadata") or {}),
        )
        _add(asset)

    for t in tasks or []:
        aid = getattr(t, "asset_id", None)
        if not aid:
            continue
        derived = Asset(
            id=str(aid),
            domain=getattr(t, "assignee_domain", "multi") or "multi",
            vehicle_type="drone" if getattr(t, "assignee_domain", "") == "air" else None,
            label=str(aid),
            status="tasked",
            route=list(getattr(t, "route", []) or []),
            metadata={"from_task": t.id},
        )
        _add(derived)

    for p in playbook_actions or []:
        params = getattr(p, "parameters", {}) if hasattr(p, "parameters") else {}
        target = params.get("target")
        if not target:
            continue
        derived = Asset(
            id=str(target),
            domain=getattr(p, "domain", "multi") or "multi",
            vehicle_type=params.get("vehicle_type"),
            label=str(target),
            status="planned",
            route=list(params.get("route") or []),
            metadata={"from_playbook": getattr(p, "id", None)},
        )
        _add(derived)

    for target, link in link_states.items():
        if target in seen:
            continue
        _add(
            Asset(
                id=target,
                domain="multi",
                label=target,
                status="link_only",
                comm_link={"source": "link_states"},
                route=[],
                link_state=_link_state_to_dict(link),
                metadata={"source": "link_states"},
            )
        )

    return assets


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

    # Optional: ingest commander intent and map to playbook actions for downstream planners.
    intents: List[Any] = []
    playbook_actions: List[Any] = []
    intent_ingest = IntentIngestService()
    playbook_mapper = PlaybookMapper()
    with metrics.timer("intent_ingest"):
        intent_path = config.get("pipeline", {}).get("intent", {}).get("path")
        intents = intent_ingest.run(intent_path, ctx)
    with metrics.timer("playbook_map"):
        if intents:
            playbook_actions = playbook_mapper.run(intents, ctx)
    if intents:
        intents_path = Path(out_dir) / "intents.json"
        intents_path.write_text(json.dumps([i.__dict__ for i in intents], indent=2), encoding="utf-8")
        audit.write("intents_written", {"path": str(intents_path), "count": len(intents)})
    if playbook_actions:
        pb_path = Path(out_dir) / "playbook_actions.json"
        pb_path.write_text(json.dumps([p.__dict__ for p in playbook_actions], indent=2), encoding="utf-8")
        audit.write("playbook_actions_written", {"path": str(pb_path), "count": len(playbook_actions)})

    rules_path = config.get("pipeline", {}).get("rules_config", "configs/rules.sample.yaml")
    engine = load_rules(rules_path)

    ingest = IngestService()
    fusion = FusionService()
    decider = DecisionService()
    autonomy = AutonomyService()
    exporter = ExportService()

    ingest_cfg = config.get("pipeline", {}).get("ingest", {})
    ingest_mode = ingest_cfg.get("mode", "scenario")
    with metrics.timer("ingest"):
        if ingest_mode == "tail":
            tail_cfg = ingest_cfg.get("tail", {})
            adapter = FileTailAdapter(
                path=tail_cfg.get("path", scenario_path),
                max_items=int(tail_cfg.get("max_items", 100)),
                poll_interval=float(tail_cfg.get("poll_interval_sec", 0.05)),
            )
            readings = adapter.collect(ctx)
        elif ingest_mode == "modules_media":
            media_cfg = ingest_cfg.get("media", {})
            modules_cfg = ingest_cfg.get("modules", {})
            media_path = media_cfg.get("path", scenario_path)
            stride = int(media_cfg.get("stride", 8))
            readings, mod_stats = collect_media_readings(media_path, stride=stride, modules_cfg=modules_cfg)
            ctx.audit.write("ingest_modules_done", {"path": media_path, "stride": stride, "stats": mod_stats})

            # Optional: derive non-identifying entity profiles from module outputs.
            # This is best-effort and must never break the pipeline.
            try:
                from .integrations.entity_profiler import write_entity_profiles

                out_path = Path(out_dir) / "entity_profiles.json"
                write_entity_profiles(readings, out_path)
                ctx.audit.write("entity_profiles_written", {"path": str(out_path)})
            except Exception as exc:  # pragma: no cover - optional output
                ctx.audit.write("entity_profiles_error", {"error": str(exc)})
        else:
            readings = ingest.run({"scenario_path": scenario_path}, ctx)

        telemetry_cfg = ingest_cfg.get("telemetry", {}) if isinstance(ingest_cfg, dict) else {}
        telemetry_path = telemetry_cfg.get("path")
        if telemetry_path:
            tail_cfg = ingest_cfg.get("tail", {}) if isinstance(ingest_cfg, dict) else {}
            tail_path = tail_cfg.get("path")
            if not tail_path or str(tail_path) != str(telemetry_path) or ingest_mode != "tail":
                telemetry_adapter = FileTailAdapter(
                    path=str(telemetry_path),
                    max_items=int(telemetry_cfg.get("max_items", 100)),
                    poll_interval=float(telemetry_cfg.get("poll_interval_sec", 0.05)),
                )
                telemetry_readings = telemetry_adapter.collect(ctx)
                if telemetry_readings:
                    readings = list(readings) + telemetry_readings
                    ctx.audit.write("ingest_telemetry", {"path": str(telemetry_path), "count": len(telemetry_readings)})
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

    # Build platform assets and commands once tasks are known.
    platform_cfg = config.get("pipeline", {}).get("platform", {})
    link_states = _load_link_states(platform_cfg)
    assets = _load_assets(platform_cfg, approved_tasks + pending_tasks, playbook_actions, link_states)

    cmd_queue = PlatformCommandQueue(platform_cfg.get("queue_path"))
    platform_commands: List[PlatformCommand] = []

    def _task_to_command(task: TaskRecommendation) -> PlatformCommand:
        target = task.asset_id or f"{task.assignee_domain}_unit"
        link_state = _link_state_to_dict(link_states.get(target))
        metadata = {"rationale": task.rationale}
        if task.link_hint:
            metadata["link_hint"] = task.link_hint
        return PlatformCommand(
            id=f"cmd_{task.id}",
            target=target,
            command=task.action,
            args={"event_id": task.event_id, "infrastructure_type": task.infrastructure_type},
            phase=None,
            priority=task.priority,
            status="queued",
            intent_id=None,
            playbook_action_id=None,
            link_window_required=bool(link_state and not link_state.get("available", True)),
            metadata=metadata,
            asset_id=task.asset_id,
            domain=task.assignee_domain,
            route=list(task.route or []),
            link_state=link_state,
        )

    for t in approved_tasks:
        platform_commands.append(_task_to_command(t))

    for p in playbook_actions:
        params = getattr(p, "parameters", {}) if hasattr(p, "parameters") else {}
        target = params.get("target") or f"{p.domain}_unit"
        link_state = _link_state_to_dict(link_states.get(target))
        platform_commands.append(
            PlatformCommand(
                id=f"cmd_{p.id}",
                target=target,
                command=p.name,
                args=params,
                phase=None,
                priority=3,
                status="queued",
                intent_id=getattr(p, "derived_from_intent", None),
                playbook_action_id=p.id,
                link_window_required=bool(link_state and not link_state.get("available", True)),
                metadata={"rationale": getattr(p, "rationale", None)},
                asset_id=params.get("asset_id") or params.get("target"),
                domain=getattr(p, "domain", None),
                route=list(params.get("route") or []),
                link_state=link_state,
            )
        )

    for cmd in platform_commands:
        cmd_queue.enqueue(cmd)

    sent, deferred = cmd_queue.attempt_send(link_states)
    if platform_commands:
        cmds_path = Path(out_dir) / "platform_commands.json"
        cmds_payload: List[Dict[str, Any]] = []
        for c in platform_commands:
            payload = dict(c.__dict__)
            if isinstance(payload.get("link_state"), LinkState):
                payload["link_state"] = _link_state_to_dict(payload.get("link_state"))
            cmds_payload.append(payload)
        cmds_path.write_text(json.dumps(cmds_payload, indent=2), encoding="utf-8")
        audit.write(
            "platform_commands",
            {
                "queued": len(platform_commands),
                "sent": len(sent),
                "deferred": len(deferred),
                "path": str(cmds_path),
            },
        )

    if assets:
        assets_path = Path(out_dir) / "assets.json"
        assets_payload = [dict(a.__dict__) for a in assets]
        assets_path.write_text(json.dumps(assets_payload, indent=2), encoding="utf-8")
        audit.write("assets_written", {"path": str(assets_path), "count": len(assets)})

    # Suggest a course of action across all module-derived outputs and tasks
    suggestion = build_action_suggestion(filtered_events, approved_tasks, pending_tasks)
    suggestion_path = Path(out_dir) / "action_suggestion.json"
    suggestion_path.write_text(json.dumps(suggestion, indent=2), encoding="utf-8")
    audit.write("action_suggestion", suggestion)

    with metrics.timer("autonomy"):
        _plan = autonomy.run(approved_tasks, ctx)
    with metrics.timer("export"):
        paths = exporter.run(
            {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "out_dir": out_dir},
            ctx,
        )

    # Optional: build a lightweight ontology graph from outputs.
    # Best-effort and must never break the pipeline.
    try:
        from .integrations.ontology_graph import write_ontology_graph

        graph_path = write_ontology_graph(
            out_dir=Path(out_dir),
            events=filtered_events,
            tasks=approved_tasks,
            pending_tasks=pending_tasks,
            platform_commands=platform_commands,
            assets=assets,
        )
        audit.write("ontology_graph_written", {"path": str(graph_path)})
    except Exception as exc:  # pragma: no cover - optional output
        audit.write("ontology_graph_error", {"error": str(exc)})

    audit.write(
        "run_end",
        {
            "events": len(filtered_events),
            "tasks": len(approved_tasks),
            "pending_tasks": len(pending_tasks),
            "metrics": metrics.snapshot(),
        },
    )
    return {"events": filtered_events, "tasks": approved_tasks, "pending_tasks": pending_tasks, "paths": paths, "metrics": metrics.snapshot(), "action_suggestion": suggestion}


def build_action_suggestion(events: List[Event], tasks: List[TaskRecommendation], pending_tasks: List[TaskRecommendation]) -> Dict[str, Any]:
    # Simple heuristic: use highest severity event category/domain, and top approved task if present
    ts = time.time()
    sev_order = {"critical": 4, "warning": 3, "notice": 2, "info": 1}
    top_event = None
    for ev in events:
        ev_sev = getattr(ev, "severity_label", None) or getattr(ev, "severity", None)
        top_sev = getattr(top_event, "severity_label", None) or getattr(top_event, "severity", None) if top_event else None
        if (top_event is None) or (sev_order.get(str(ev_sev), 0) > sev_order.get(str(top_sev), 0)):
            top_event = ev
    recommended = None
    if tasks:
        t = tasks[0]
        recommended = {
            "action": getattr(t, "action", "observe") or "observe",
            "asset_id": getattr(t, "asset_id", None) or "unknown_asset",
            "infrastructure_type": getattr(t, "infrastructure_type", None) or "infra",
            "assignee_domain": getattr(t, "assignee_domain", None) or "unknown",
            "rationale": getattr(t, "rationale", ""),
        }
    elif pending_tasks:
        t = pending_tasks[0]
        recommended = {
            "action": getattr(t, "action", "observe") or "observe",
            "asset_id": getattr(t, "asset_id", None) or "unknown_asset",
            "infrastructure_type": getattr(t, "infrastructure_type", None) or "infra",
            "assignee_domain": getattr(t, "assignee_domain", None) or "unknown",
            "rationale": getattr(t, "rationale", ""),
        }
    summary = {
        "events_seen": len(events),
        "tasks_approved": len(tasks),
        "tasks_pending": len(pending_tasks),
        "top_event": {
            "id": getattr(top_event, "id", None) if top_event else None,
            "category": getattr(top_event, "category", None) if top_event else None,
            "domain": getattr(top_event, "domain", None) if top_event else None,
            "severity": (getattr(top_event, "severity_label", None) or getattr(top_event, "severity", None)) if top_event else None,
        },
    }
    text = "Hold position and continue observation."
    if recommended:
        text = f"Proceed to {recommended['action']} {recommended['asset_id']} ({recommended['infrastructure_type']}) for domain {recommended['assignee_domain']}."
    elif top_event and str(summary["top_event"]["severity"]).lower() == "critical":
        text = "Escalate to security lead and lock down affected assets."

    return {
        "id": f"suggestion-{int(ts)}",
        "proposed_at": ts,
        "status": "proposed",
        "recommended": recommended,
        "summary": summary,
        "plain_text": text,
    }
