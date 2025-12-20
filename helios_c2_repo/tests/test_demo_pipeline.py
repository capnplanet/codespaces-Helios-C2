from helios_c2.orchestrator import load_config, run_pipeline


def test_pipeline_runs_minimal(tmp_path):
    cfg = load_config("configs/default.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert "events" in result and "tasks" in result
    assert len(result["events"]) >= 1
    assert len(result["tasks"]) >= 1
