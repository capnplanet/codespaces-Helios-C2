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

    args = p.parse_args()

    cfg = load_config(args.config)
    os.makedirs(args.out, exist_ok=True)

    run_pipeline(config=cfg, scenario_path=args.scenario, out_dir=args.out)


if __name__ == "__main__":
    main()
