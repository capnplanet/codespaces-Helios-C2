from __future__ import annotations
import argparse
import json
import os
from typing import Any, Dict, List, Tuple

from .orchestrator import load_config, run_pipeline


def _parse_arm_specs(specs: List[str]) -> List[Tuple[str, str]]:
    arms: List[Tuple[str, str]] = []
    seen_names = set()
    for raw in specs:
        if ":" not in raw:
            raise ValueError(f"Invalid --arm value '{raw}'. Expected format NAME:CONFIG_PATH")
        name, config_path = raw.split(":", 1)
        name = name.strip()
        config_path = config_path.strip()
        if not name or not config_path:
            raise ValueError(f"Invalid --arm value '{raw}'. Expected format NAME:CONFIG_PATH")
        if name in seen_names:
            raise ValueError(f"Duplicate arm name '{name}'")
        seen_names.add(name)
        arms.append((name, config_path))
    return arms


def _summarize_arm(out_dir: str) -> Dict[str, Any]:
    events_path = os.path.join(out_dir, "events.json")
    audit_path = os.path.join(out_dir, "audit_log.jsonl")
    summary: Dict[str, Any] = {
        "events": 0,
        "tasks": 0,
        "pending_tasks": 0,
        "risk_hold_tasks": 0,
        "approved_tasks": 0,
        "audit_entries": 0,
        "has_metrics": os.path.exists(os.path.join(out_dir, "metrics.prom")),
    }

    if os.path.exists(events_path):
        try:
            data = json.loads(open(events_path, "r", encoding="utf-8").read())
            events = data.get("events", [])
            tasks = data.get("tasks", [])
            pending = data.get("pending_tasks", [])
            summary["events"] = len(events)
            summary["tasks"] = len(tasks)
            summary["pending_tasks"] = len(pending)
            all_tasks = list(tasks) + list(pending)
            summary["risk_hold_tasks"] = sum(1 for t in all_tasks if (t or {}).get("status") == "risk_hold")
            summary["approved_tasks"] = sum(1 for t in tasks if (t or {}).get("status") == "approved")
        except Exception:
            pass

    if os.path.exists(audit_path):
        try:
            with open(audit_path, "r", encoding="utf-8", errors="ignore") as f:
                summary["audit_entries"] = sum(1 for _ in f)
        except Exception:
            pass

    return summary


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

    arms = sub.add_parser(
        "simulate_arms",
        help="Run one scenario across multiple config arms and write per-arm outputs + a comparison summary.",
    )
    arms.add_argument("--scenario", required=True, help="Path to scenario YAML file.")
    arms.add_argument("--out", required=True, help="Output directory root for arm subdirectories.")
    arms.add_argument(
        "--arm",
        action="append",
        default=[],
        help="Arm definition in NAME:CONFIG_PATH format. Repeat for multiple arms.",
    )
    arms.add_argument("--approver-id", default=None, help="Approver ID for signed approvals (optional).")
    arms.add_argument("--approver-token", default=None, help="HMAC token for approvals (optional).")

    args = p.parse_args()

    if args.cmd == "simulate":
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
        return

    if args.cmd == "simulate_arms":
        parsed_arms = _parse_arm_specs(list(args.arm))
        if not parsed_arms:
            raise SystemExit("simulate_arms requires at least one --arm NAME:CONFIG_PATH")

        os.makedirs(args.out, exist_ok=True)
        comparison: Dict[str, Any] = {
            "scenario": args.scenario,
            "arms": {},
        }

        for arm_name, config_path in parsed_arms:
            cfg = load_config(config_path)
            if args.approver_id and args.approver_token:
                cfg.setdefault("pipeline", {}).setdefault("rbac", {}).setdefault("active_approver", {})["id"] = args.approver_id
                cfg["pipeline"]["rbac"]["active_approver"]["token"] = args.approver_token

            arm_out = os.path.join(args.out, f"arm_{arm_name}")
            os.makedirs(arm_out, exist_ok=True)
            run_pipeline(config=cfg, scenario_path=args.scenario, out_dir=arm_out)
            comparison["arms"][arm_name] = {
                "config": config_path,
                "out_dir": arm_out,
                "summary": _summarize_arm(arm_out),
            }

        summary_path = os.path.join(args.out, "comparison_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)
        return

    raise SystemExit(f"Unsupported command: {args.cmd}")


if __name__ == "__main__":
    main()
