from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class SoftBiometricVector:
    height_px: float
    aspect_ratio: float
    area_px: float

    def as_array(self) -> np.ndarray:
        return np.array(
            [self.height_px, self.aspect_ratio, self.area_px], dtype=np.float32
        )


def compute_soft_biometrics(bbox: Tuple[int, int, int, int]) -> SoftBiometricVector:
    x, y, w, h = bbox
    area = float(w * h)
    ar = h / max(w, 1)
    return SoftBiometricVector(height_px=float(h), aspect_ratio=float(ar), area_px=area)
