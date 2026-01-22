from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

from ..utils import validate_json


@dataclass
class VehicleState:
    asset_id: str
    domain: str
    vehicle_type: str | None
    label: str
    lat: float
    lon: float
    alt_m: float | None
    battery_pct: float | None
    status: str
    comm_link: Dict[str, Any]
    route: List[Dict[str, Any]]
    last_command: str | None = None


def _resolve_config_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    project_root = Path(__file__).resolve().parents[3]
    candidate = project_root / p
    if candidate.exists():
        return candidate
    return p


def _load_config(path: str) -> Dict[str, Any]:
    resolved = _resolve_config_path(path)
    with resolved.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _pick_home(asset: Dict[str, Any]) -> tuple[float, float, float | None]:
    home = asset.get("home_wp") or (asset.get("route") or [{}])[0] or {}
    lat = float(home.get("lat", 34.0522 + random.uniform(-0.002, 0.002)))
    lon = float(home.get("lon", -118.2437 + random.uniform(-0.002, 0.002)))
    alt = home.get("alt_m")
    return lat, lon, float(alt) if alt is not None else None


def _build_states(config: Dict[str, Any]) -> Dict[str, VehicleState]:
    platform_cfg = config.get("pipeline", {}).get("platform", {})
    states: Dict[str, VehicleState] = {}
    for idx, asset in enumerate(platform_cfg.get("assets", []) or []):
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id") or f"asset_{idx}")
        lat, lon, alt = _pick_home(asset)
        states[asset_id] = VehicleState(
            asset_id=asset_id,
            domain=str(asset.get("domain") or "multi"),
            vehicle_type=asset.get("vehicle_type"),
            label=str(asset.get("label") or asset_id),
            lat=lat,
            lon=lon,
            alt_m=alt,
            battery_pct=asset.get("battery_pct"),
            status=str(asset.get("status") or "available"),
            comm_link=dict(asset.get("comm_link") or {}),
            route=list(asset.get("route") or []),
        )
    return states


def _load_commands(commands_path: Path) -> List[Dict[str, Any]]:
    if not commands_path.exists():
        return []
    try:
        raw = json.loads(commands_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return raw.get("commands") or []
    except Exception:
        return []
    return []


def _apply_command(state: VehicleState, command: Dict[str, Any]) -> None:
    text = str(command.get("command") or "").lower()
    if not text:
        return
    state.last_command = text
    if "hold" in text or "loiter" in text:
        state.status = "holding"
        return
    if "move" in text or "advance" in text or "patrol" in text:
        state.status = "moving"
        return


def _step_state(state: VehicleState, moving_speed: float) -> None:
    drift = moving_speed if state.status == "moving" else moving_speed * 0.2
    state.lat += random.uniform(-1, 1) * drift
    state.lon += random.uniform(-1, 1) * drift
    if state.battery_pct is not None:
        state.battery_pct = max(0.0, float(state.battery_pct) - random.uniform(0.0005, 0.002))


def _build_reading(state: VehicleState, ts_ms: int) -> Dict[str, Any]:
    reading = {
        "id": f"telemetry_{state.asset_id}_{ts_ms}",
        "sensor_id": f"{state.asset_id}_telemetry",
        "domain": state.domain,
        "source_type": "telemetry",
        "ts_ms": ts_ms,
        "geo": {"lat": state.lat, "lon": state.lon, "alt_m": state.alt_m},
        "details": {
            "asset_id": state.asset_id,
            "asset": {
                "id": state.asset_id,
                "domain": state.domain,
                "vehicle_type": state.vehicle_type,
                "label": state.label,
                "status": state.status,
                "battery_pct": state.battery_pct,
                "comm_link": state.comm_link,
                "route": state.route,
            },
            "telemetry": {
                "last_command": state.last_command,
                "status": state.status,
            },
        },
    }
    validate_json("sensor_reading.schema.json", reading)
    return reading


def _write_assets(assets_path: Path, states: Dict[str, VehicleState]) -> None:
    payload: List[Dict[str, Any]] = []
    for state in states.values():
        payload.append(
            {
                "id": state.asset_id,
                "domain": state.domain,
                "vehicle_type": state.vehicle_type,
                "label": state.label,
                "status": state.status,
                "battery_pct": state.battery_pct,
                "comm_link": state.comm_link,
                "route": state.route,
                "metadata": {"telemetry_ts_ms": int(time.time() * 1000)},
            }
        )
    assets_path.parent.mkdir(parents=True, exist_ok=True)
    assets_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_simulator(config_path: str, out_dir: str, interval_sec: float, max_delta: float) -> None:
    config = _load_config(config_path)
    states = _build_states(config)
    out_root = Path(out_dir)
    ingest_cfg = config.get("pipeline", {}).get("ingest", {})
    telemetry_cfg = ingest_cfg.get("telemetry", {}) if isinstance(ingest_cfg, dict) else {}
    telemetry_path = telemetry_cfg.get("path") or ingest_cfg.get("tail", {}).get("path") or (out_root / "telemetry.jsonl")
    telemetry_path = Path(telemetry_path)
    commands_path = out_root / "platform_commands.json"
    assets_path = out_root / "assets.json"

    applied: set[str] = set()

    while True:
        commands = _load_commands(commands_path)
        for cmd in commands:
            cmd_id = str(cmd.get("id") or "")
            if cmd_id and cmd_id in applied:
                continue
            target = str(cmd.get("target") or cmd.get("asset_id") or "")
            if target and target in states:
                _apply_command(states[target], cmd)
                if cmd_id:
                    applied.add(cmd_id)

        ts_ms = int(time.time() * 1000)
        readings: List[Dict[str, Any]] = []
        for state in states.values():
            _step_state(state, max_delta)
            readings.append(_build_reading(state, ts_ms))

        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_path.open("a", encoding="utf-8") as f:
            for reading in readings:
                f.write(json.dumps(reading) + "\n")

        _write_assets(assets_path, states)
        time.sleep(interval_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulated backend vehicle telemetry generator")
    parser.add_argument("--config", default="configs/default.yaml", help="Config path")
    parser.add_argument("--out", dest="out_dir", default="out", help="Output directory")
    parser.add_argument("--interval", type=float, default=1.0, help="Telemetry interval seconds")
    parser.add_argument("--max-delta", type=float, default=0.0003, help="Max lat/lon drift per tick")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_simulator(args.config, args.out_dir, args.interval, args.max_delta)


if __name__ == "__main__":
    main()
