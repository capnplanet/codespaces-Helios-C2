from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..gait.gait_features import GaitSequence, gait_feature_from_sequence
from ..vision.clothing_features import ClothingDescriptor
from ..vision.soft_biometrics import SoftBiometricVector


@dataclass
class FusedFeatures:
    gait: np.ndarray
    soft_biometrics: np.ndarray
    clothing: np.ndarray

    def as_array(self) -> np.ndarray:
        return np.concatenate([self.gait, self.soft_biometrics, self.clothing], axis=0)

    def to_dict(self) -> dict:
        return {
            "gait": self.gait.tolist(),
            "soft_biometrics": self.soft_biometrics.tolist(),
            "clothing": self.clothing.tolist(),
        }

    @staticmethod
    def from_dict(payload: dict) -> "FusedFeatures":
        return FusedFeatures(
            gait=np.array(payload.get("gait", []), dtype=np.float32),
            soft_biometrics=np.array(payload.get("soft_biometrics", []), dtype=np.float32),
            clothing=np.array(payload.get("clothing", []), dtype=np.float32),
        )


def fuse_features(
    gait_seq: GaitSequence,
    soft_vector: SoftBiometricVector,
    clothing_desc: Optional[ClothingDescriptor] = None,
) -> FusedFeatures:
    gait_vec = gait_feature_from_sequence(gait_seq)
    soft_vec = soft_vector.as_array()
    clothing_vec = (
        clothing_desc.as_array() if clothing_desc is not None else np.zeros(24, dtype=np.float32)
    )
    return FusedFeatures(gait=gait_vec, soft_biometrics=soft_vec, clothing=clothing_vec)
