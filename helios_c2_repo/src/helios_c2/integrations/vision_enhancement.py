from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_video_frames(path: str, *, deinterlace: bool = False, max_frames: int | None = None) -> tuple[List[np.ndarray], float]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    frames: List[np.ndarray] = []
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if deinterlace:
                frame = _deinterlace(frame)
            frames.append(frame)
            idx += 1
            if max_frames is not None and idx >= int(max_frames):
                break
    finally:
        cap.release()
    return frames, fps


def _deinterlace(frame: np.ndarray) -> np.ndarray:
    even = frame[0::2]
    odd = frame[1::2]
    interp = (even.astype(np.float32) * 0.5 + odd.astype(np.float32) * 0.5).astype(np.uint8)
    merged = np.zeros_like(frame)
    merged[0::2] = interp
    merged[1::2] = interp
    return merged


def write_video_frames(frames: List[np.ndarray], path: str, fps: float) -> None:
    if not frames:
        raise ValueError("No frames to write")
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps or 25.0), (w, h))
    if not writer.isOpened():
        raise RuntimeError("OpenCV VideoWriter failed to open (mp4v codec unavailable)")
    try:
        for fr in frames:
            writer.write(fr)
    finally:
        writer.release()


def stabilize_frames(frames: List[np.ndarray]) -> tuple[List[np.ndarray], Dict[str, float]]:
    if not frames:
        return [], {"residual_motion": 0.0}
    ref = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(500)
    aligned = [frames[0]]
    residuals: List[float] = []
    for idx in range(1, len(frames)):
        gray = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2GRAY)
        k1, d1 = orb.detectAndCompute(ref, None)
        k2, d2 = orb.detectAndCompute(gray, None)
        if d1 is None or d2 is None:
            aligned.append(frames[idx])
            residuals.append(0.0)
            continue
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = sorted(bf.match(d1, d2), key=lambda m: m.distance)
        pts1 = np.float32([k1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        pts2 = np.float32([k2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        if len(pts1) < 4:
            aligned.append(frames[idx])
            residuals.append(0.0)
            continue
        matrix, _ = cv2.estimateAffinePartial2D(pts2, pts1, method=cv2.RANSAC)
        if matrix is None:
            aligned.append(frames[idx])
            residuals.append(0.0)
            continue
        h, w = ref.shape[:2]
        stabilized = cv2.warpAffine(frames[idx], matrix, (w, h))
        aligned.append(stabilized)
        residuals.append(float(np.linalg.norm(matrix - np.eye(2, 3))))
    return aligned, {"residual_motion": float(np.mean(residuals) if residuals else 0.0)}


def temporal_denoise(frames: List[np.ndarray], window: int = 2) -> tuple[List[np.ndarray], Dict[str, float]]:
    if not frames:
        return [], {"snr_gain": 0.0}
    out: List[np.ndarray] = []
    gains: List[float] = []
    for i in range(len(frames)):
        s = max(0, i - window)
        e = min(len(frames), i + window + 1)
        stack = np.stack(frames[s:e]).astype(np.float32)
        median = np.median(stack, axis=0)
        out.append(np.clip(median, 0, 255).astype(np.uint8))
        gains.append(float(np.sqrt(stack.shape[0])))
    return out, {"snr_gain": float(np.mean(gains) if gains else 0.0)}


def unsharp_mask(frames: List[np.ndarray], amount: float = 0.8) -> List[np.ndarray]:
    out: List[np.ndarray] = []
    for fr in frames:
        blur = cv2.GaussianBlur(fr, (0, 0), sigmaX=1.2)
        out.append(cv2.addWeighted(fr, 1 + float(amount), blur, -float(amount), 0))
    return out


_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _detect_faces(frame: np.ndarray) -> List[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(24, 24))
    boxes: List[tuple[int, int, int, int]] = []
    for (x, y, w, h) in faces:
        boxes.append((int(x), int(y), int(x + w), int(y + h)))
    return boxes


def redact_faces(frames: List[np.ndarray]) -> List[np.ndarray]:
    out: List[np.ndarray] = []
    for fr in frames:
        boxes = _detect_faces(fr)
        blurred = fr.copy()
        for x1, y1, x2, y2 in boxes:
            roi = blurred[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            blurred[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (21, 21), 0)
        out.append(blurred)
    return out


def create_montage(frames: List[np.ndarray], cols: int = 3) -> np.ndarray:
    if not frames:
        raise ValueError("No frames for montage")
    rows = int(np.ceil(len(frames) / float(cols)))
    h, w = frames[0].shape[:2]
    montage = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for idx, fr in enumerate(frames):
        r = idx // cols
        c = idx % cols
        montage[r * h : (r + 1) * h, c * w : (c + 1) * w] = fr
    return montage


def run_enhancement(
    video_path: str,
    *,
    out_dir: Path | str,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    cfg = dict(config or {})
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    request_id = cfg.get("request_id") or f"req-{uuid.uuid4().hex[:10]}"

    frames, fps = read_video_frames(
        video_path,
        deinterlace=bool(cfg.get("deinterlace", False)),
        max_frames=cfg.get("max_frames"),
    )

    if bool(cfg.get("stabilize", True)):
        frames, stab_report = stabilize_frames(frames)
    else:
        stab_report = {"residual_motion": 0.0}

    frames, denoise_report = temporal_denoise(frames, window=int(cfg.get("denoise_window", 2)))
    frames = unsharp_mask(frames, amount=float(cfg.get("sharpen_amount", 0.8)))

    # Conservative upsample: deterministic resize only (no ML hallucination risk).
    scale = int(cfg.get("sr_scale", 2))
    if scale > 1 and frames:
        frames = [cv2.resize(f, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) for f in frames]

    if bool(cfg.get("redact_faces", False)):
        frames = redact_faces(frames)

    enhanced_video = out_dir / f"enhanced_{request_id}.mp4"
    montage_path = out_dir / f"montage_{request_id}.jpg"
    metadata_path = out_dir / f"metadata_{request_id}.json"

    montage = create_montage(frames[: min(len(frames), 9)], cols=3) if frames else np.zeros((1, 1, 3), dtype=np.uint8)
    cv2.imwrite(str(montage_path), montage)
    write_video_frames(frames, str(enhanced_video), fps)

    metadata = {
        "schema_version": "0.1",
        "request_id": request_id,
        "created_at": time.time(),
        "config": cfg,
        "inputs": {"video_path": video_path, "sha256": _sha256_file(video_path)},
        "reports": {"stabilization": stab_report, "denoise": denoise_report},
        "outputs": {
            "video": str(enhanced_video),
            "montage": str(montage_path),
            "metadata": str(metadata_path),
        },
        "disclaimer": "Conservative deterministic enhancement; no ML-assisted super-resolution.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "request_id": request_id,
        "video": str(enhanced_video),
        "montage": str(montage_path),
        "metadata": str(metadata_path),
    }
