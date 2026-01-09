from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class Detection:
    frame_index: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    score: float


class PersonDetector:
    """Deterministic person detector using a fixed HOG + SVM model.

    OpenCV ships a pre-trained, CPU-only HOG person detector. We keep all
    parameters static to maintain reproducibility and apply a light NMS pass to
    reduce duplicate boxes. This avoids the placeholder background subtraction
    while staying dependency-light.
    """

    def __init__(
        self,
        hit_threshold: float = 0.0,
        win_stride: Tuple[int, int] = (8, 8),
        padding: Tuple[int, int] = (8, 8),
        scale: float = 1.05,
        group_threshold: int = 2,
        nms_threshold: float = 0.35,
    ):
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._hit_threshold = hit_threshold
        self._win_stride = win_stride
        self._padding = padding
        self._scale = scale
        self._group_threshold = group_threshold
        self._nms_threshold = nms_threshold

    @staticmethod
    def _nms(boxes: List[Tuple[int, int, int, int]], scores: List[float], threshold: float) -> List[int]:
        if not boxes:
            return []
        x1 = np.array([b[0] for b in boxes], dtype=np.float32)
        y1 = np.array([b[1] for b in boxes], dtype=np.float32)
        x2 = x1 + np.array([b[2] for b in boxes], dtype=np.float32)
        y2 = y1 + np.array([b[3] for b in boxes], dtype=np.float32)
        scores_np = np.array(scores, dtype=np.float32)

        idxs = scores_np.argsort()[::-1]
        keep: List[int] = []
        while idxs.size > 0:
            i = int(idxs[0])
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[idxs[1:]])
            yy1 = np.maximum(y1[i], y1[idxs[1:]])
            xx2 = np.minimum(x2[i], x2[idxs[1:]])
            yy2 = np.minimum(y2[i], y2[idxs[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            intersection = w * h
            area_i = (x2[i] - x1[i]) * (y2[i] - y1[i])
            area_rest = (x2[idxs[1:]] - x1[idxs[1:]]) * (y2[idxs[1:]] - y1[idxs[1:]])
            union = area_i + area_rest - intersection + 1e-6
            overlap = intersection / union

            idxs = idxs[1:][overlap <= threshold]
        return keep

    def detect(self, frame: np.ndarray, frame_index: int) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rects, weights = self._hog.detectMultiScale(
            gray,
            hitThreshold=self._hit_threshold,
            winStride=self._win_stride,
            padding=self._padding,
            scale=self._scale,
            groupThreshold=self._group_threshold,
        )

        boxes = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in rects]
        scores = [float(s) if s is not None else 0.0 for s in (weights or [])]
        keep = self._nms(boxes, scores, self._nms_threshold)

        detections = [
            Detection(frame_index=frame_index, bbox=boxes[i], score=scores[i])
            for i in keep
        ]
        detections.sort(key=lambda d: (d.frame_index, -d.score, d.bbox[0], d.bbox[1]))
        return detections
