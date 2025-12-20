import time
import json
from helios_c2.audit import AuditLogger
from helios_c2.orchestrator import load_config, run_pipeline


def test_audit_hash_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(path))
    logger.write("test", {"a": 1})
    logger.write("test2", {"b": 2})

    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert "hash" in first and first["hash"]
    assert second.get("prev_hash") == first.get("hash")


def test_risk_budget_hold(tmp_path):
    cfg = load_config("configs/default.yaml")
    guardrails = cfg.setdefault("pipeline", {}).setdefault("guardrails", {})
    guardrails.setdefault("risk_budgets", {}).setdefault("default", {})["critical_limit"] = 0
    guardrails["risk_backoff_base_sec"] = 1

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    pending = result.get("pending_tasks", [])
    assert any(t.status == "risk_hold" for t in pending)
    for t in pending:
        if t.status == "risk_hold":
            assert t.hold_until_epoch and t.hold_until_epoch > time.time()
