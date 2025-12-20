from __future__ import annotations

"""Adapter that runs the migrated media modules and emits SensorReading objects.

This keeps Helios governance/decision logic intact while letting rich
vision/audio/thermal extracts enter through the normal ingest path.
"""

from pathlib import Path
import time
from typing import List, Dict, Any

from helios_c2.types import SensorReading
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


def _now_ms() -> int:
    return int(time.time() * 1000)


def collect_media_readings(media_path: str, stride: int = 8) -> List[SensorReading]:
    path = Path(media_path)
    if not path.exists():
        raise FileNotFoundError(f"Media path not found: {path}")

    ts0 = _now_ms()
    readings: List[SensorReading] = []

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
    detections = list(vision_detect.detect_frames(path, stride=stride, downscale=0.75, motion_gate=True))
    if detections:
        add("vision", "video", {"detections": detections})
        tracks = track_reid.track_and_reid(detections)
        add("vision", "tracking", {"tracks": tracks})
        plates = ocr_alpr.ocr_plates(path, tracks)
        if plates:
            add("vision", "alpr", {"plates": plates})
        gait_embs = gait.extract_gait_embeddings(detections)
        if gait_embs:
            add("vision", "gait", {"gait_embeddings": gait_embs})
        # Scene graph synthesis for downstream summaries
        scene = fuse_scene.build_scene_graph(tracks, plates, {"segments": []}, [], [], {}, media_path=path)
        add("scene", "fused_scene", scene)

    # Audio
    sounds = audio_sed.detect_sounds(path)
    if sounds:
        add("audio", "sed", {"sounds": sounds})
    transcript = audio_asr.transcribe(path)
    if transcript:
        add("audio", "asr", transcript)

    # Action recognition
    actions = action_recog.classify_actions(path)
    if actions:
        add("vision", "action", {"actions": actions})

    # Thermal
    thermal = thermal_ir.analyze(path, stride=max(1, stride // 2))
    if thermal:
        add("thermal", "thermal_ir", thermal)

    return readings
