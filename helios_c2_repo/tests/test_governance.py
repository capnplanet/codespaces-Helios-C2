from helios_c2.orchestrator import load_config, run_pipeline


def test_governance_blocks_domains(tmp_path):
    cfg = load_config("configs/default.yaml")
    cfg.setdefault("pipeline", {}).setdefault("governance", {})["block_domains"] = ["air"]

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    assert all(ev.domain != "air" for ev in result["events"])
    assert len(result["tasks"]) == len(result["events"])


def test_governance_caps_severity(tmp_path):
    cfg = load_config("configs/default.yaml")
    gov_cfg = cfg.setdefault("pipeline", {}).setdefault("governance", {})
    gov_cfg["severity_caps"] = {"human": "warning"}

    out_dir = tmp_path / "out2"
    out_dir.mkdir()

    result = run_pipeline(cfg, "examples/scenario_minimal.yaml", str(out_dir))
    severities = {ev.domain: ev.severity for ev in result["events"] if ev.domain == "human"}
    assert severities.get("human") == "warning"
