from __future__ import annotations

"""Adapter that runs the migrated media modules and emits SensorReading objects.

This keeps Helios governance/decision logic intact while letting rich
vision/audio/thermal extracts enter through the normal ingest path.
"""

from pathlib import Path
import time
from typing import List, Dict, Any, Tuple

from helios_c2.types import SensorReading


def _now_ms() -> int:
    return int(time.time() * 1000)


def collect_media_readings(
    media_path: str,
    stride: int = 8,
    modules_cfg: Dict[str, Any] | None = None,
) -> Tuple[List[SensorReading], Dict[str, int]]:
    path = Path(media_path)
    if not path.exists():
        raise FileNotFoundError(f"Media path not found: {path}")

    ts0 = _now_ms()
    readings: List[SensorReading] = []
    stats: Dict[str, int] = {"vision": 0, "audio": 0, "thermal": 0, "scene": 0}

    cfg = modules_cfg or {}
    enable_vision = bool(cfg.get("enable_vision", True))
    enable_audio = bool(cfg.get("enable_audio", True))
    enable_thermal = bool(cfg.get("enable_thermal", True))
    enable_gait = bool(cfg.get("enable_gait", True))
    enable_scene = bool(cfg.get("enable_scene", True))
    downscale = float(cfg.get("downscale", 0.75))

    # Import heavy optional deps only when the adapter is actually used.
    from helios_c2.modules import (
        vision_detect,
        track_reid,
        ocr_alpr,
        audio_sed,
        audio_asr,
        action_recog,
        thermal_ir,
        gait,
        fuse_scene,
    )

    def add(domain: str, source_type: str, details: Dict[str, Any]):
        rid = f"{domain}_{len(readings):05d}"
        readings.append(
            SensorReading(
                id=rid,
                sensor_id=domain,
                domain=domain,
                source_type=source_type,
                ts_ms=ts0 + len(readings),
                details=details,
            )
        )

    # Vision frames + tracking + plate OCR + gait
    if enable_vision:
        detections = list(vision_detect.detect_frames(path, stride=stride, downscale=downscale, motion_gate=True))
        if detections:
            add("vision", "video", {"detections": detections}); stats["vision"] += 1
            tracks = track_reid.track_and_reid(detections)
            add("vision", "tracking", {"tracks": tracks}); stats["vision"] += 1
            plates = ocr_alpr.ocr_plates(path, tracks)
            if plates:
                add("vision", "alpr", {"plates": plates}); stats["vision"] += 1
            if enable_gait:
                gait_embs = gait.extract_gait_embeddings(detections)
                if gait_embs:
                    add("vision", "gait", {"gait_embeddings": gait_embs}); stats["vision"] += 1
            if enable_scene:
                scene = fuse_scene.build_scene_graph(tracks, plates, {"segments": []}, [], [], {}, media_path=path)
                add("scene", "fused_scene", scene); stats["scene"] += 1

    # Audio
    if enable_audio:
        sounds = audio_sed.detect_sounds(path)
        if sounds:
            add("audio", "sed", {"sounds": sounds}); stats["audio"] += 1
        transcript = audio_asr.transcribe(path)
        if transcript:
            add("audio", "asr", transcript); stats["audio"] += 1

    # Action recognition
    if enable_vision:
        actions = action_recog.classify_actions(path)
        if actions:
            add("vision", "action", {"actions": actions}); stats["vision"] += 1

    # Thermal
    if enable_thermal:
        thermal = thermal_ir.analyze(path, stride=max(1, stride // 2))
        if thermal:
            add("thermal", "thermal_ir", thermal); stats["thermal"] += 1

    return readings, stats
