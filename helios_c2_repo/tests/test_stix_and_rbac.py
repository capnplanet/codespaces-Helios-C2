import base64
import hmac
import hashlib
import json
from pathlib import Path

from helios_c2.orchestrator import load_config, run_pipeline


def _token(secret: str, message: str) -> str:
    mac = hmac.new(secret.encode(), msg=message.encode(), digestmod=hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def test_stix_export(tmp_path):
    cfg = load_config("configs/default.yaml")
    cfg.setdefault("pipeline", {}).setdefault("export", {})["formats"] = ["stix"]
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    stix_path = out_dir / "events_stix.json"
    assert stix_path.exists()
    bundle = json.loads(stix_path.read_text(encoding="utf-8"))
    assert bundle.get("type") == "bundle"
    assert bundle.get("objects")
    assert any(obj.get("type") == "observed-data" for obj in bundle.get("objects", []))


def test_dual_approval_signed(tmp_path):
    cfg = load_config("configs/default.yaml")
    pipe = cfg.setdefault("pipeline", {})
    pipe.setdefault("human_loop", {})["allow_unsigned_auto_approve"] = False
    pipe.setdefault("rbac", {})["required_roles"] = {"air": ["ops"]}
    pipe["rbac"]["approvers"] = [
        {"id": "approver1", "secret": "s1", "roles": ["ops"]},
    ]

    # Precompute token for expected message: event id uses rule id and reading id
    message = "ev_r1_air_low_altitude_unknown:air:investigate:default"
    token = _token("s1", message)
    pipe["rbac"]["active_approvers"] = [{"id": "approver1", "token": token}]
    cfg["pipeline"]["export"] = {"formats": ["json"]}

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    tasks = result["tasks"]
    assert tasks, "tasks should be produced"
    for t in tasks:
        if t.assignee_domain == "air":
            assert t.status == "approved"
            assert t.approved_by == "approver1"


def test_risk_store_persistence(tmp_path):
    cfg = load_config("configs/default.yaml")
    guardrails = cfg.setdefault("pipeline", {}).setdefault("guardrails", {})
    guardrails["risk_budgets"] = {"default": {"critical_limit": 0}}
    guardrails["risk_store_path"] = str(tmp_path / "store.sqlite")
    guardrails["risk_window_sec"] = 10_000
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # First run
    res1 = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert any(t.status == "risk_hold" for t in res1.get("pending_tasks", []))
    # Second run should still see holds due to persisted counts
    res2 = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert any(t.status == "risk_hold" for t in res2.get("pending_tasks", []))
