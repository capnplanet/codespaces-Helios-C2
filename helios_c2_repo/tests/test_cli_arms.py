import json
from pathlib import Path

import pytest

from helios_c2 import cli


def test_parse_arm_specs_valid_and_duplicate_rejected():
    parsed = cli._parse_arm_specs(["baseline:configs/default.yaml", "strict:configs/policy_safety.yaml"])
    assert parsed == [
        ("baseline", "configs/default.yaml"),
        ("strict", "configs/policy_safety.yaml"),
    ]

    with pytest.raises(ValueError):
        cli._parse_arm_specs(["broken-format"])

    with pytest.raises(ValueError):
        cli._parse_arm_specs(["a:one.yaml", "a:two.yaml"])


def test_simulate_arms_writes_comparison_summary(monkeypatch, tmp_path):
    calls = []

    def fake_load_config(path):
        return {"config_path": path}

    def fake_run_pipeline(config, scenario_path, out_dir):
        calls.append((config, scenario_path, out_dir))
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        events_blob = {
            "events": [{"id": "e1"}],
            "tasks": [{"id": "t1", "status": "approved"}],
            "pending_tasks": [{"id": "t2", "status": "risk_hold"}],
        }
        (out / "events.json").write_text(json.dumps(events_blob), encoding="utf-8")
        (out / "audit_log.jsonl").write_text('{"event":"run_start"}\n{"event":"run_end"}\n', encoding="utf-8")
        (out / "metrics.prom").write_text("helios_events_total 1\n", encoding="utf-8")

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    out_dir = tmp_path / "arms_out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "helios-c2",
            "simulate_arms",
            "--scenario",
            "examples/scenario_minimal.yaml",
            "--out",
            str(out_dir),
            "--arm",
            "baseline:configs/default.yaml",
            "--arm",
            "strict:configs/policy_safety.yaml",
        ],
    )

    cli.main()

    assert len(calls) == 2

    summary_path = out_dir / "comparison_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["scenario"] == "examples/scenario_minimal.yaml"
    assert set(summary["arms"].keys()) == {"baseline", "strict"}

    baseline = summary["arms"]["baseline"]
    assert baseline["config"] == "configs/default.yaml"
    assert baseline["summary"]["events"] == 1
    assert baseline["summary"]["tasks"] == 1
    assert baseline["summary"]["pending_tasks"] == 1
    assert baseline["summary"]["approved_tasks"] == 1
    assert baseline["summary"]["risk_hold_tasks"] == 1
    assert baseline["summary"]["audit_entries"] == 2
    assert baseline["summary"]["has_metrics"] is True


def test_simulate_arms_requires_arm(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "helios-c2",
            "simulate_arms",
            "--scenario",
            "examples/scenario_minimal.yaml",
            "--out",
            str(tmp_path / "out"),
        ],
    )

    with pytest.raises(SystemExit):
        cli.main()
