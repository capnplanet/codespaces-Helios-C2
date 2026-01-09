from dataclasses import dataclass
from typing import List

import numpy as np

from ..vision.pose_estimation import Pose


@dataclass
class GaitSequence:
    entity_id: str | None
    poses: List[Pose]


def gait_feature_from_sequence(sequence: GaitSequence) -> np.ndarray:
    """Compute a simple deterministic gait feature from a sequence of poses."""
    if not sequence.poses:
        return np.zeros(10, dtype=np.float32)

    joints_stack = np.stack([p.joints for p in sequence.poses], axis=0)
    torso_len = np.mean(
        np.linalg.norm(joints_stack[:, 1, :] - joints_stack[:, 8, :], axis=-1) + 1e-6
    )
    norm_joints = joints_stack / torso_len

    mean_coords = norm_joints.mean(axis=(0, 1))
    std_coords = norm_joints.std(axis=(0, 1))

    if norm_joints.shape[0] < 2:
        speed_mean = 0.0
        speed_std = 0.0
    else:
        vel = np.diff(norm_joints, axis=0)
        speed = np.linalg.norm(vel, axis=-1).mean(axis=1)
        speed_mean = float(speed.mean())
        speed_std = float(speed.std())

    return np.array(
        [
            float(mean_coords[0]),
            float(mean_coords[1]),
            float(std_coords[0]),
            float(std_coords[1]),
            speed_mean,
            speed_std,
            float(len(sequence.poses)),
            float(torso_len),
            0.0,
            0.0,
        ],
        dtype=np.float32,
    )
