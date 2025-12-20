import base64
import hmac
import hashlib
from pathlib import Path

from helios_c2.orchestrator import apply_risk_budget
from helios_c2.types import Event, TaskRecommendation
from helios_c2.services.decider import DecisionService
from helios_c2.services.base import ServiceContext
from helios_c2.audit import AuditLogger
from helios_c2.governance import Governance, GovernanceConfig
from helios_c2.metrics import Metrics
from helios_c2.adapters.file_tail import FileTailAdapter


def _token(msg: str, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), msg=msg.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("utf-8").rstrip("=")


def test_risk_budget_persists_across_runs(tmp_path):
    cfg = {
        "pipeline": {
            "guardrails": {
                "risk_budgets": {"default": {"critical_limit": 1}},
                "risk_store_path": str(tmp_path / "risk.sqlite"),
                "risk_window_sec": 300,
            }
        }
    }

    ev = Event(
        id="e1",
        category="intrusion",
        severity="critical",
        status="open",
        domain="facility",
        summary="test",
        time_window={"start": 0, "end": 1},
    )
    task = TaskRecommendation(
        id="t1",
        event_id="e1",
        action="investigate",
        assignee_domain="facility",
        priority=1,
        rationale="test",
        confidence=0.9,
        tenant="default",
    )

    events_by_id = {ev.id: ev}

    first, stats1 = apply_risk_budget([task], events_by_id, cfg)
    assert first[0].status == "approved"
    assert stats1["counts"].get("default") == 1

    second_task = TaskRecommendation(**task.__dict__)
    second, stats2 = apply_risk_budget([second_task], events_by_id, cfg)
    assert second[0].status == "risk_hold"
    assert stats2["counts"].get("default") >= 2


def test_dual_approval_required_roles(tmp_path):
    secret1 = "s1"
    secret2 = "s2"
    cfg = {
        "severity": {"info": 1, "warning": 3, "critical": 4},
        "pipeline": {
            "human_loop": {"default_require_approval": True, "auto_approve": True, "allow_unsigned_auto_approve": False},
            "rbac": {
                "min_approvals": 2,
                "approvers": [
                    {"id": "a1", "secret": secret1, "roles": ["ops"]},
                    {"id": "a2", "secret": secret2, "roles": ["sec"]},
                ],
                "active_approvers": [],
                "required_roles": {"facility": ["ops", "sec"]},
            },
        },
        "tenant": {"id": "default"},
    }

    event = Event(
        id="ev1",
        category="alert",
        severity="critical",
        status="open",
        domain="facility",
        summary="dual approval",
        time_window={"start": 0, "end": 1},
    )

    message = f"{event.id}:{event.domain}:investigate:default"
    cfg["pipeline"]["rbac"]["active_approvers"] = [
        {"id": "a1", "token": _token(message, secret1)},
        {"id": "a2", "token": _token(message, secret2)},
    ]

    ctx = ServiceContext(config=cfg, audit=AuditLogger(str(tmp_path / "audit.jsonl")), governance=Governance(GovernanceConfig()), metrics=Metrics())
    tasks = DecisionService().run([event], ctx)
    assert tasks[0].status == "approved"
    assert set(tasks[0].approved_by.split(",")) == {"a1", "a2"}


def test_audit_chain_verification(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(audit_path), sign_secret="secret", verify_on_start=False)
    logger.write("test", {"ok": True})
    logger.write("test2", {"ok": True})
    assert logger.verify_chain()


def test_tail_ingest_schema_validation(tmp_path):
    src = tmp_path / "feed.jsonl"
    src.write_text(
        "\n".join(
            [
                '{"id": "r1", "sensor_id": "s", "domain": "air", "source_type": "radar", "ts_ms": 1}',
                '{"id": "r2", "sensor_id": "s2", "domain": "land", "source_type": "cam", "ts_ms": 2}',
            ]
        )
    )
    adapter = FileTailAdapter(str(src), max_items=10, poll_interval=0)
    ctx = ServiceContext(config={}, audit=AuditLogger(str(tmp_path / "audit.jsonl")), governance=Governance(GovernanceConfig()), metrics=Metrics())
    readings = adapter.collect(ctx)
    assert len(readings) == 2


def test_export_schema(tmp_path):
    # Minimal export validation path using decision/risk outputs
    from helios_c2.services.exporter import ExportService

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    ctx = ServiceContext(config={}, audit=AuditLogger(str(out_dir / "audit.jsonl")), governance=Governance(GovernanceConfig()), metrics=Metrics())
    ev = Event(
        id="e1",
        category="c",
        severity="info",
        status="open",
        domain="facility",
        summary="s",
        time_window={"start": 0, "end": 1},
    )
    task = TaskRecommendation(
        id="t1",
        event_id="e1",
        action="investigate",
        assignee_domain="facility",
        priority=1,
        rationale="r",
        confidence=0.5,
    )
    exp = ExportService()
    paths = exp.run({"events": [ev], "tasks": [task], "pending_tasks": [], "out_dir": str(out_dir)}, ctx)
    assert "json" in paths
    assert Path(paths["json"]).exists()
    # ensure content loads
    import json

    data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert data["events"][0]["id"] == "e1"
