from helios_c2.orchestrator import load_config, run_pipeline


def test_rate_limits_drop_tasks(tmp_path):
    cfg = load_config("configs/default.yaml")
    pipeline = cfg.setdefault("pipeline", {})
    pipeline.setdefault("guardrails", {}).setdefault("rate_limits", {})["total"] = 1
    pipeline["guardrails"]["rate_limits"]["per_event"] = 1

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert len(result["tasks"]) == 1


def test_human_loop_pending(tmp_path):
    cfg = load_config("configs/default.yaml")
    hl = cfg.setdefault("pipeline", {}).setdefault("human_loop", {})
    hl["auto_approve"] = False
    hl["domain_require_approval"] = ["facility", "air", "cyber", "human"]

    out_dir = tmp_path / "out2"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert len(result["tasks"]) == 0
    assert len(result["pending_tasks"]) >= 1
