import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np


def read_video_frames(path: str, deinterlace: bool = False) -> Tuple[List[np.ndarray], float]:
    cap = cv2.VideoCapture(path)
    frames: List[np.ndarray] = []
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if deinterlace:
            frame = _deinterlace(frame)
        frames.append(frame)
    cap.release()
    return frames, fps


def _deinterlace(frame: np.ndarray) -> np.ndarray:
    even = frame[0::2]
    odd = frame[1::2]
    interp = (even.astype(np.float32) * 0.5 + odd.astype(np.float32) * 0.5).astype(
        np.uint8
    )
    merged = np.zeros_like(frame)
    merged[0::2] = interp
    merged[1::2] = interp
    return merged


def write_video_frames(frames: List[np.ndarray], path: str, fps: float) -> None:
    if not frames:
        raise ValueError("No frames to write")
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    for frame in frames:
        writer.write(frame)
    writer.release()


def stabilize_frames(frames: List[np.ndarray]) -> Tuple[List[np.ndarray], Dict[str, float]]:
    if not frames:
        return [], {"residual_motion": 0.0}
    ref = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(500)
    aligned: List[np.ndarray] = [frames[0]]
    residuals: List[float] = []
    for idx in range(1, len(frames)):
        gray = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2GRAY)
        kpts1, desc1 = orb.detectAndCompute(ref, None)
        kpts2, desc2 = orb.detectAndCompute(gray, None)
        if desc1 is None or desc2 is None:
            aligned.append(frames[idx])
            residuals.append(0.0)
            continue
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(desc1, desc2)
        matches = sorted(matches, key=lambda x: x.distance)
        pts1 = np.float32([kpts1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        pts2 = np.float32([kpts2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
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
        delta = np.linalg.norm(matrix - np.eye(2, 3))
        residuals.append(float(delta))
    return aligned, {"residual_motion": float(np.mean(residuals) if residuals else 0.0)}


def temporal_denoise(frames: List[np.ndarray], window: int = 2) -> Tuple[List[np.ndarray], Dict[str, float]]:
    if not frames:
        return [], {"snr_gain": 0.0}
    denoised: List[np.ndarray] = []
    gains: List[float] = []
    for i in range(len(frames)):
        start = max(0, i - window)
        end = min(len(frames), i + window + 1)
        stack = np.stack(frames[start:end]).astype(np.float32)
        median = np.median(stack, axis=0)
        denoised.append(np.clip(median, 0, 255).astype(np.uint8))
        local_gain = float(np.sqrt(stack.shape[0]))
        gains.append(local_gain)
    return denoised, {"snr_gain": float(np.mean(gains))}


def unsharp_mask(frames: List[np.ndarray], amount: float = 1.0) -> List[np.ndarray]:
    output: List[np.ndarray] = []
    for frame in frames:
        blur = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.2)
        sharpened = cv2.addWeighted(frame, 1 + amount, blur, -amount, 0)
        output.append(sharpened)
    return output


def temporal_super_res(frames: List[np.ndarray], scale: int = 2) -> Tuple[List[np.ndarray], np.ndarray]:
    if not frames:
        return [], np.zeros((1, 1), dtype=np.float32)
    upsampled = [cv2.resize(f, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) for f in frames]
    accumulator = np.zeros_like(upsampled[0], dtype=np.float32)
    for idx, frame in enumerate(upsampled):
        weight = 1.0 / (idx + 1)
        accumulator = accumulator * (1 - weight) + frame.astype(np.float32) * weight
    mean = accumulator / np.max(accumulator.clip(min=1.0))
    confidence = cv2.cvtColor(mean.astype(np.float32), cv2.COLOR_BGR2GRAY)
    confidence = cv2.normalize(confidence, None, 0, 1, cv2.NORM_MINMAX)
    return [accumulator.clip(0, 255).astype(np.uint8)], confidence


def create_montage(frames: List[np.ndarray], cols: int = 3) -> np.ndarray:
    if not frames:
        raise ValueError("No frames for montage")
    rows = int(np.ceil(len(frames) / cols))
    h, w = frames[0].shape[:2]
    montage = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for idx, frame in enumerate(frames):
        r = idx // cols
        c = idx % cols
        montage[r * h : (r + 1) * h, c * w : (c + 1) * w] = frame
    return montage


def save_image(path: str, img: np.ndarray) -> None:
    cv2.imwrite(path, img)


def blend_uncertainty(base: np.ndarray, alt: np.ndarray) -> np.ndarray:
    diff = cv2.absdiff(base, alt)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    heatmap = cv2.applyColorMap(cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX), cv2.COLORMAP_JET)
    return heatmap
