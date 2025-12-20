from pathlib import Path

from helios_c2.orchestrator import load_config, run_pipeline


def test_infrastructure_tasks_and_export(tmp_path):
    cfg = load_config("configs/default.yaml")
    export_cfg = cfg.setdefault("pipeline", {}).setdefault("export", {})
    export_cfg["formats"] = ["json", "infrastructure"]
    export_cfg["infrastructure"] = {"path": str(tmp_path / "infra_actions.jsonl")}

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_infra.yaml", str(out_dir))

    infra_tasks = [t for t in result["tasks"] if getattr(t, "infrastructure_type", None)]
    assert infra_tasks, "Expected infrastructure tasks to be produced"

    infra_file = tmp_path / "infra_actions.jsonl"
    assert infra_file.exists(), "Infrastructure actions file should be written"
    lines = infra_file.read_text(encoding="utf-8").strip().split("\n")
    assert lines, "Infrastructure actions file should contain entries"

    # ensure at least one lock and one notify action are present
    actions = ["lock" in line or "notify_emergency_services" in line or "notify_security" in line for line in lines]
    assert any(actions)
