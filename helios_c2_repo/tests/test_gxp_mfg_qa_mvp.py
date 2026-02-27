from helios_c2.orchestrator import load_config, run_pipeline


def test_gxp_mfg_qa_scenario_runs(tmp_path):
    cfg = load_config("configs/gxp_mfg_qa.yaml")
    out_dir = tmp_path / "out_gxp"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_gxp_mfg_qa.yaml", str(out_dir))

    assert result["events"], "expected at least one event"
    categories = {ev.category for ev in result["events"]}
    assert "qa_oos" in categories or "critical_quality_risk" in categories

    all_tasks = list(result["tasks"]) + list(result.get("pending_tasks", []))
    infra_actions = {getattr(t, "action", None) for t in all_tasks if getattr(t, "infrastructure_type", None)}
    assert "hold_batch" in infra_actions
    assert "open_deviation" in infra_actions or "start_capa" in infra_actions


def test_gxp_multi_arm_summary_contains_gxp_arm(monkeypatch, tmp_path):
    from helios_c2 import cli
    import json

    out_dir = tmp_path / "out_arms"
    monkeypatch.setattr(
        "sys.argv",
        [
            "helios-c2",
            "simulate_arms",
            "--scenario",
            "examples/scenario_gxp_mfg_qa.yaml",
            "--out",
            str(out_dir),
            "--arm",
            "baseline:configs/default.yaml",
            "--arm",
            "gxp:configs/gxp_mfg_qa.yaml",
        ],
    )

    cli.main()

    summary = json.loads((out_dir / "comparison_summary.json").read_text(encoding="utf-8"))
    assert "gxp" in summary["arms"]
    assert summary["arms"]["gxp"]["summary"]["events"] >= 1
