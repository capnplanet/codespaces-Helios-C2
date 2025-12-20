import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from helios_c2.orchestrator import load_config, run_pipeline, apply_guardrails
from helios_c2.types import TaskRecommendation, Event
from helios_c2.services.base import ServiceContext
from helios_c2.governance import Governance, GovernanceConfig
from helios_c2.audit import AuditLogger
from helios_c2.metrics import Metrics


def test_infrastructure_http_effector(monkeypatch, tmp_path):
    sent = []

    def fake_urlopen(req, timeout=5):
        sent.append(json.loads(req.data.decode("utf-8")))
        return SimpleNamespace(__enter__=lambda s: s, __exit__=lambda *a, **k: False)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    cfg = load_config("configs/default.yaml")
    export_cfg = cfg.setdefault("pipeline", {}).setdefault("export", {})
    export_cfg["formats"] = ["infrastructure"]
    export_cfg["infrastructure"] = {
        "path": str(tmp_path / "infra.jsonl"),
        "http": {"url": "http://example.test/mock", "timeout_seconds": 5, "retries": 0},
    }

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    run_pipeline(cfg, "examples/scenario_infra.yaml", str(out_dir))

    assert sent, "Expected HTTP effector to send payload"
    payload = sent[0]
    assert isinstance(payload, list)
    assert any("lock" in json.dumps(p) for p in payload)


def test_infrastructure_per_asset_limit():
    cfg = {"pipeline": {"guardrails": {"rate_limits": {"per_asset_infra": {"gate_alpha": 0}}}}}
    ev = Event(
        id="e1",
        category="facility_intrusion",
        severity="warning",
        status="open",
        domain="facility",
        summary="",
        time_window={"start_ms": 0, "end_ms": 1},
    )
    t1 = TaskRecommendation(
        id="t1",
        event_id=ev.id,
        action="lock",
        assignee_domain="facility",
        priority=1,
        rationale="",
        confidence=0.9,
        infrastructure_type="gate",
        asset_id="gate_alpha",
    )
    kept, stats = apply_guardrails([t1], {"pipeline": cfg["pipeline"]})
    assert not kept
    assert stats.get("per_asset_infra") == 1


def test_infrastructure_required_roles(tmp_path):
    secret = "s1"
    cfg = load_config("configs/default.yaml")
    infra = cfg.setdefault("pipeline", {}).setdefault("infrastructure", {})
    infra["mappings"] = [
        {
            "match": {"category": "facility_intrusion", "domain": "facility"},
            "tasks": [
                {
                    "action": "lock",
                    "asset_id": "gate_alpha",
                    "infrastructure_type": "gate",
                    "rationale": "contain",
                    "assignee_domain": "facility",
                    "priority": 1,
                    "requires_approval": True,
                    "required_roles": ["sec"],
                    "min_approvals": 1,
                }
            ],
        }
    ]
    rbac = cfg.setdefault("pipeline", {}).setdefault("rbac", {})
    rbac["approvers"] = [{"id": "a1", "secret": secret, "roles": ["sec"]}]
    token_msg = "ev_g1_facility_tailgating:facility:lock:default"
    import hmac, hashlib, base64

    token = base64.urlsafe_b64encode(hmac.new(secret.encode(), msg=token_msg.encode(), digestmod=hashlib.sha256).digest()).decode().rstrip("=")
    rbac["active_approvers"] = [{"id": "a1", "token": token}]
    cfg["pipeline"]["export"]["formats"] = ["json"]

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_infra.yaml", str(out_dir))
    infra_tasks = [t for t in result["tasks"] if getattr(t, "infrastructure_type", None)]
    assert infra_tasks, "expected infra tasks"
    assert infra_tasks[0].status == "approved"
    assert infra_tasks[0].approved_by