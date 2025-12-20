from __future__ import annotations
import argparse
import os

from .orchestrator import load_config, run_pipeline


def main() -> None:
    p = argparse.ArgumentParser(prog="helios-c2")
    sub = p.add_subparsers(dest="cmd", required=True)

    sim = sub.add_parser("simulate", help="Run a synthetic Helios C2 scenario.")
    sim.add_argument("--scenario", required=True, help="Path to scenario YAML file.")
    sim.add_argument("--out", required=True, help="Output directory.")
    sim.add_argument("--config", default="configs/default.yaml", help="Path to config YAML.")
    sim.add_argument("--policy-pack", default=None, help="Optional policy pack YAML to merge (governance/human_loop/guardrails).")
    sim.add_argument("--approver-id", default=None, help="Approver ID for signed approvals (optional).")
    sim.add_argument("--approver-token", default=None, help="HMAC token for approvals (optional).")

    args = p.parse_args()

    cfg = load_config(args.config)
    if args.policy_pack:
        from .orchestrator import load_policy, merge_policy

        pol = load_policy(args.policy_pack)
        cfg = merge_policy(cfg, pol)

    if args.approver_id and args.approver_token:
        cfg.setdefault("pipeline", {}).setdefault("rbac", {}).setdefault("active_approver", {})["id"] = args.approver_id
        cfg["pipeline"]["rbac"]["active_approver"]["token"] = args.approver_token
    os.makedirs(args.out, exist_ok=True)

    run_pipeline(config=cfg, scenario_path=args.scenario, out_dir=args.out)


if __name__ == "__main__":
    main()
