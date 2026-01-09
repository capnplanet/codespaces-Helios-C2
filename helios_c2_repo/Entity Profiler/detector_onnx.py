from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import cv2

from ..config import Paths

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - handled gracefully when missing
    ort = None


@dataclass
class Detection:
    frame_index: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    score: float


class OnnxPersonDetector:
    """Minimal ONNX-backed detector. Expects output in (N, 6): x1,y1,x2,y2,score,class.

    If the model or runtime is unavailable, detect() returns an empty list to allow fallback use.
    Place your detector at models/detector.onnx (or pass a custom path) with a single input.
    """

    def __init__(self, model_path: Path | None = None, score_threshold: float = 0.25):
        if model_path is None:
            model_path = Paths().models_dir / "detector.onnx"
        self.model_path = Path(model_path)
        self.score_threshold = score_threshold
        self._session = None
        self._input_name = None
        self._runtime_available = ort is not None and self.model_path.exists()
        if self._runtime_available:
            self._session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
            self._input_name = self._session.get_inputs()[0].name

    def _preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32)
        # naive resize/pad to square 640 keeping aspect ratio
        size = 640
        scale = min(size / w, size / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(rgb, (nw, nh))
        canvas = np.zeros((size, size, 3), dtype=np.float32)
        top, left = (size - nh) // 2, (size - nw) // 2
        canvas[top:top+nh, left:left+nw, :] = resized
        # normalize to 0-1
        canvas /= 255.0
        # NCHW
        chw = np.transpose(canvas, (2, 0, 1))[np.newaxis, ...]
        return chw, (left, top, scale)

    def _postprocess(self, outputs: np.ndarray, pad: Tuple[int, int, float], orig_shape: Tuple[int, int]) -> List[Detection]:
        left, top, scale = pad
        h, w = orig_shape
        dets: List[Detection] = []
        if outputs.ndim == 3:
            outputs = outputs[0]
        for row in outputs:
            if row.shape[0] < 6:
                continue
            x1, y1, x2, y2, score, cls = row[:6]
            if score < self.score_threshold:
                continue
            # only keep person class (assume 0) if available
            if cls not in (0, 0.0, 0.0):
                continue
            # map back to image coords
            x1 = (x1 - left) / scale
            y1 = (y1 - top) / scale
            x2 = (x2 - left) / scale
            y2 = (y2 - top) / scale
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))
            bw = max(1, x2 - x1)
            bh = max(1, y2 - y1)
            dets.append(Detection(frame_index=0, bbox=(int(x1), int(y1), int(bw), int(bh)), score=float(score)))
        dets.sort(key=lambda d: -d.score)
        return dets

    def detect(self, frame: np.ndarray, frame_index: int) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []
        if not self._runtime_available or self._session is None:
            return []
        batch, pad = self._preprocess(frame)
        try:
            outputs = self._session.run(None, {self._input_name: batch})[0]
        except Exception:
            return []
        dets = self._postprocess(outputs, pad, frame.shape[:2])
        for d in dets:
            d.frame_index = frame_index
        return dets
