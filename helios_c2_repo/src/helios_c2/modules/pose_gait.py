from __future__ import annotations

"""Pose-based non-identifying gait feature extraction using MediaPipe Pose.

Origin: MediaPipe (Google, USA). Extracts coarse movement descriptors only.
NO identity inference; outputs track-like aggregates across consecutive frames.
"""

from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

mp_pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                 enable_segmentation=False, min_detection_confidence=0.5,
                                 min_tracking_confidence=0.5)


POSE_LANDMARKS_USED = {
    'left_ankle': mp.solutions.pose.PoseLandmark.LEFT_ANKLE,
    'right_ankle': mp.solutions.pose.PoseLandmark.RIGHT_ANKLE,
    'left_hip': mp.solutions.pose.PoseLandmark.LEFT_HIP,
    'right_hip': mp.solutions.pose.PoseLandmark.RIGHT_HIP,
}


@dataclass
class PoseFrame:
    frame_idx: int
    landmarks: Dict[str, tuple[float, float, float]]  # x,y,visibility


def extract_pose_frames(video_path: Path, stride: int = 1, downscale: float = 0.75, max_frames: int | None = None) -> List[PoseFrame]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video for pose: {video_path}")
    frames: List[PoseFrame] = []
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride != 0:
                idx += 1
                continue
            if downscale != 1.0:
                frame = cv2.resize(frame, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = mp_pose.process(rgb)
            if res.pose_landmarks:
                lm_dict: Dict[str, tuple[float, float, float]] = {}
                for name, enum_val in POSE_LANDMARKS_USED.items():
                    lm = res.pose_landmarks.landmark[enum_val]
                    lm_dict[name] = (lm.x, lm.y, lm.visibility)
                frames.append(PoseFrame(frame_idx=idx, landmarks=lm_dict))
            idx += 1
            if max_frames and idx >= max_frames:
                break
    finally:
        cap.release()
    return frames


def _valid_pair(lms: Dict[str, tuple[float, float, float]], a: str, b: str, vis_thresh: float = 0.5) -> bool:
    return a in lms and b in lms and lms[a][2] >= vis_thresh and lms[b][2] >= vis_thresh


def pose_gait_metrics(frames: List[PoseFrame]) -> Dict[str, object]:
    if not frames:
        return {"pose_tracks": [], "summary": {}}
    # Treat consecutive frames with landmarks as one track (single subject assumption)
    frames_sorted = sorted(frames, key=lambda f: f.frame_idx)
    # Compute stride proxy: ankle horizontal distance oscillation
    ankle_dists = []
    hip_centers = []
    for pf in frames_sorted:
        lms = pf.landmarks
        if _valid_pair(lms, 'left_ankle', 'right_ankle'):
            ax = lms['left_ankle'][0] - lms['right_ankle'][0]
            ankle_dists.append(abs(ax))
        if _valid_pair(lms, 'left_hip', 'right_hip'):
            hx = (lms['left_hip'][0] + lms['right_hip'][0]) / 2.0
            hy = (lms['left_hip'][1] + lms['right_hip'][1]) / 2.0
            hip_centers.append((hx, hy))
    hip_centers_np = np.array(hip_centers, dtype=np.float32)
    speeds = []
    if len(hip_centers_np) >= 2:
        diffs = np.linalg.norm(np.diff(hip_centers_np, axis=0), axis=1)
        speeds = diffs.tolist()
    # Cadence proxy via ankle distance oscillation frequency
    cadence = 0.0
    if len(ankle_dists) >= 30:
        series = np.array(ankle_dists, dtype=np.float32) - float(np.mean(ankle_dists))
        window = np.hanning(len(series))
        spec = np.fft.rfft(series * window)
        mags = np.abs(spec)
        mags[0] = 0.0
        k = int(np.argmax(mags))
        freq = k / float(len(series))
        if freq < 0.5:
            cadence = freq
    track = {
        "length_frames": len(frames_sorted),
        "mean_speed_center": float(np.mean(speeds)) if speeds else 0.0,
        "std_speed_center": float(np.std(speeds)) if speeds else 0.0,
        "ankle_dist_mean": float(np.mean(ankle_dists)) if ankle_dists else 0.0,
        "ankle_dist_std": float(np.std(ankle_dists)) if ankle_dists else 0.0,
        "cadence_proxy": float(cadence),
        "landmark_coverage": float(len(frames_sorted)) / float(frames_sorted[-1].frame_idx - frames_sorted[0].frame_idx + 1),
    }
    return {
        "pose_tracks": [track],
        "summary": {
            "frames_with_pose": len(frames_sorted),
            "cadence_proxy": track["cadence_proxy"],
            "mean_speed_center": track["mean_speed_center"],
        }
    }
