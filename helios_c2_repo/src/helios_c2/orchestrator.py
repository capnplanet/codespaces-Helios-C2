from __future__ import annotations
from typing import Any, Dict, List
import os
import yaml

from .audit import AuditLogger
from .governance import Governance, GovernanceConfig
from .rules_engine import RulesEngine, Rule
from .services.base import ServiceContext
from .services.ingest import IngestService
from .services.fusion import FusionService
from .services.decider import DecisionService
from .services.autonomy import AutonomyService
from .services.exporter import ExportService
from .types import Event
from .utils import sha256_json


SCHEMA_VERSION = "0.1"


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rules(path: str) -> RulesEngine:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    rules: List[Rule] = []
    for item in raw.get("rules", []):
        rules.append(Rule(id=item["id"], when=item["when"], then=item["then"]))
    return RulesEngine(rules)


def run_pipeline(config: Dict[str, Any], scenario_path: str, out_dir: str) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    audit = AuditLogger(os.path.join(out_dir, "audit_log.jsonl"))
    gov_cfg = GovernanceConfig(
        forbid_actions=config.get("pipeline", {}).get("governance", {}).get("forbid_actions", [])
    )
    governance = Governance(gov_cfg)
    ctx = ServiceContext(config=config, audit=audit, governance=governance)

    audit.write(
        "run_start",
        {
            "schema_version": SCHEMA_VERSION,
            "config_hash": sha256_json(config),
            "scenario": scenario_path,
        },
    )

    rules_path = config.get("pipeline", {}).get("rules_config", "configs/rules.sample.yaml")
    engine = load_rules(rules_path)

    ingest = IngestService()
    fusion = FusionService()
    decider = DecisionService()
    autonomy = AutonomyService()
    exporter = ExportService()

    readings = ingest.run({"scenario_path": scenario_path}, ctx)
    fused = fusion.run(readings, ctx)
    events = engine.apply(fused["readings"])
    audit.write("rules_done", {"events": len(events)})
    tasks = decider.run(events, ctx)
    _plan = autonomy.run(tasks, ctx)
    paths = exporter.run({"events": events, "tasks": tasks, "out_dir": out_dir}, ctx)

    audit.write("run_end", {"events": len(events), "tasks": len(tasks)})
    return {"events": events, "tasks": tasks, "paths": paths}
