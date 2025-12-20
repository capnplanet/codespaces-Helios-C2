from __future__ import annotations

"""Robust non-identifying signature builder with EMA + colorless digest.

Attempts to reduce sensitivity to clothing changes by using channel ratio averages,
HOG-like coarse cell orientation sketch, and a color-insensitive digest path.
"""

import hashlib
import random
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2


class RobustSignatureBuilder:
    def __init__(self, ema_alpha: float = 0.3, hog_cells: tuple[int, int] = (4, 4), seed: int = 7):
        self.ema_alpha = ema_alpha
        self.hog_cells = hog_cells
        random.seed(seed)
        self._salts = [random.getrandbits(32) for _ in range(32)]
        # EMAs
        self.height_ema: Optional[float] = None
        self.speed_ema: Optional[float] = None
        self.edge_ema: Optional[float] = None
        self.landmark_cov_ema: Optional[float] = None
        self.color_ratios_accum: List[List[float]] = []
        self.last_sig: Dict[str, float] | None = None

    def _update_ema(self, current: float, prev: Optional[float]) -> float:
        if prev is None:
            return current
        return prev * (1 - self.ema_alpha) + current * self.ema_alpha

    def _color_ratios(self, roi: np.ndarray) -> List[float]:
        means = [float(roi[:, :, c].mean()) + 1e-3 for c in range(3)]
        total = sum(means)
        return [m / total for m in means]

    def _hog_indices(self, gray: np.ndarray) -> List[int]:
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        h, w = gray.shape
        cx, cy = self.hog_cells
        cell_w = max(1, w // cx)
        cell_h = max(1, h // cy)
        out: List[int] = []
        for yy in range(cy):
            for xx in range(cx):
                x1 = xx * cell_w
                y1 = yy * cell_h
                x2 = min(w, x1 + cell_w)
                y2 = min(h, y1 + cell_h)
                mc = mag[y1:y2, x1:x2]
                ac = ang[y1:y2, x1:x2]
                if mc.size == 0:
                    out.append(0)
                    continue
                bins = 8
                bw = 360.0 / bins
                hist = np.zeros(bins, dtype=np.float32)
                for a, mm in zip(ac.flatten(), mc.flatten()):
                    bi = int(a // bw) % bins
                    hist[bi] += mm
                out.append(int(hist.argmax()))
        return out

    def _minhash(self, values: List[int]) -> List[int]:
        sig = []
        for salt in self._salts:
            m = None
            for v in values:
                h = (v ^ salt) & 0xFFFFFFFF
                if m is None or h < m:
                    m = h
            sig.append(m if m is not None else 0)
        return sig[:16]

    def _quantize(self, value: float, bins: int, vmin: float, vmax: float) -> int:
        if value < vmin:
            value = vmin
        if value > vmax:
            value = vmax
        step = (vmax - vmin) / float(bins)
        return int((value - vmin) // step) if step > 0 else 0

    def update(self, frame: np.ndarray, bbox: tuple[float, float, float, float],
               height_norm: float, speed_norm: float, edge_density: float, landmark_cov: float) -> Dict[str, object]:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        X1 = max(0, int(x1 * w)); X2 = max(0, min(w, int(x2 * w)))
        Y1 = max(0, int(y1 * h)); Y2 = max(0, min(h, int(y2 * h)))
        if X2 <= X1 or Y2 <= Y1:
            roi = frame[0:1, 0:1, :]
        else:
            upper_h = Y1 + int((Y2 - Y1) * 0.55)
            upper_h = min(Y2, upper_h)
            roi = frame[Y1:upper_h, X1:X2, :]
            if roi.size == 0:
                roi = frame[0:1, 0:1, :]

        ratios = self._color_ratios(roi)
        self.color_ratios_accum.append(ratios)
        avg_color = np.mean(self.color_ratios_accum, axis=0) if self.color_ratios_accum else [0, 0, 0]

        self.height_ema = self._update_ema(height_norm, self.height_ema)
        self.speed_ema = self._update_ema(speed_norm, self.speed_ema)
        self.edge_ema = self._update_ema(edge_density, self.edge_ema)
        self.landmark_cov_ema = self._update_ema(landmark_cov, self.landmark_cov_ema)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hog_indices = self._hog_indices(gray)

        vec_ints: List[int] = [
            self._quantize(self.height_ema or 0.0, 12, 0.25, 1.0),
            self._quantize(self.speed_ema or 0.0, 12, 0.0, 0.05),
            self._quantize(self.edge_ema or 0.0, 10, 0.0, 0.20),
            self._quantize(self.landmark_cov_ema or 0.0, 6, 0.0, 1.0),
        ]
        for c in avg_color:
            vec_ints.append(self._quantize(float(c), 8, 0.0, 1.0))
        vec_ints.extend(hog_indices)

        mh = self._minhash(vec_ints)
        raw = ",".join(map(str, vec_ints)) + "|" + ",".join(map(str, mh))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        ci_vec = vec_ints[:4] + hog_indices  # colorless
        ci_raw = ",".join(map(str, ci_vec)) + "|" + ",".join(map(str, mh))
        colorless_digest = hashlib.sha256(ci_raw.encode("utf-8")).hexdigest()[:32]

        sig = {
            "digest": digest,
            "colorless_digest": colorless_digest,
            "minhash": mh,
            "hog_indices": hog_indices,
            "height_ema": self.height_ema,
            "speed_ema": self.speed_ema,
            "edge_ema": self.edge_ema,
            "landmark_cov_ema": self.landmark_cov_ema,
            "avg_color_ratios": list(avg_color),
            "vector_ints": vec_ints,
        }
        self.last_sig = sig
        return sig
