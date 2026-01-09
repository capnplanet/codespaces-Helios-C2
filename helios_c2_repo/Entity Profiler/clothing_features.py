from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class ClothingDescriptor:
    color_hist: np.ndarray
    texture_hist: np.ndarray

    def as_array(self) -> np.ndarray:
        return np.concatenate([self.color_hist, self.texture_hist]).astype(np.float32)


def extract_clothing_features(
    frame: np.ndarray, bbox: Tuple[int, int, int, int]
) -> ClothingDescriptor:
    x, y, w, h = bbox
    patch = frame[y : y + h, x : x + w]
    if patch.size == 0:
        patch = np.zeros((64, 32, 3), dtype=np.uint8)
    patch = cv2.resize(patch, (32, 64))

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()

    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    if mag.max() <= 0:
        tex_hist = np.zeros(16, dtype=np.float32)
    else:
        tex_hist, _ = np.histogram(
            mag, bins=16, range=(0, float(mag.max())), density=True
        )

    return ClothingDescriptor(color_hist=hist, texture_hist=tex_hist)
