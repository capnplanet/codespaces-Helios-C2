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
class Pose:
    frame_index: int
    bbox: Tuple[int, int, int, int]
    joints: np.ndarray  # shape (num_joints, 2) in image pixel coords


class PoseEstimator:
    """Pose estimator backed by an ONNX model when available.

    If the ONNX runtime or model file is missing, this falls back to returning
    an empty list to keep the rest of the pipeline operational. Drop a model at
    `models/pose_estimator.onnx` to enable real pose estimation.
    """

    def __init__(
        self,
        num_joints: int = 17,
        model_path: Path | None = None,
        input_size: int = 256,
        bbox_expand: float = 1.2,
    ):
        self.num_joints = num_joints
        self.input_size = input_size
        self.bbox_expand = bbox_expand

        if model_path is None:
            model_path = Paths().models_dir / "pose_estimator.onnx"
        self.model_path = Path(model_path)

        self._runtime_available = ort is not None and self.model_path.exists()
        self._session = None
        self._input_name = None
        self._output_name = None

        if self._runtime_available:
            self._session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"]
            )
            self._input_name = self._session.get_inputs()[0].name
            self._output_name = self._session.get_outputs()[0].name

    def _preprocess(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]):
        h, w = frame.shape[:2]
        x, y, bw, bh = bbox

        # expand box
        cx, cy = x + bw / 2.0, y + bh / 2.0
        new_w, new_h = bw * self.bbox_expand, bh * self.bbox_expand
        x1 = int(max(0, cx - new_w / 2.0))
        y1 = int(max(0, cy - new_h / 2.0))
        x2 = int(min(w, cx + new_w / 2.0))
        y2 = int(min(h, cy + new_h / 2.0))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            crop = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        crop = cv2.resize(crop, (self.input_size, self.input_size))

        # BGR -> RGB and normalize to [0,1]
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        chw = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]  # NCHW
        return chw, (x1, y1, x2, y2)

    def _postprocess(self, keypoints_norm: np.ndarray, crop_box: Tuple[int, int, int, int]) -> np.ndarray:
        x1, y1, x2, y2 = crop_box
        crop_w = max(x2 - x1, 1)
        crop_h = max(y2 - y1, 1)
        # keypoints_norm expected in [0,1] for x,y
        xs = keypoints_norm[:, 0] * crop_w + x1
        ys = keypoints_norm[:, 1] * crop_h + y1
        return np.stack([xs, ys], axis=-1).astype(np.float32)

    def _normalize_output(self, raw: np.ndarray) -> np.ndarray:
        """Normalize model output to (num_joints, 2) in [0,1].

        Many pose models output (N, J, 3) with (y, x, score) or (N, J, 2) with
        (y, x). We coerce to (J, 2) ordered as (x, y) normalized.
        """
        if raw.ndim == 3:
            # Assume (J, 3) or (J, 2) for a single sample already sliced
            pass
        elif raw.ndim == 4:
            # e.g., (1, J, 3, 1) or similar; squeeze
            raw = np.squeeze(raw, axis=0)

        if raw.shape[-1] == 3:
            # raw format (y, x, score)
            norm = raw[:, [1, 0]]  # (x, y)
        else:
            norm = raw[:, :2]  # assume (y, x) or (x, y)
            # if likely (y, x), swap
            if np.mean(norm[:, 0]) < np.mean(norm[:, 1]):
                norm = norm[:, [1, 0]]
        norm = norm.astype(np.float32)
        # Clamp to [0,1]
        norm = np.clip(norm, 0.0, 1.0)
        return norm

    def estimate(
        self, frame: np.ndarray, bboxes: List[Tuple[int, int, int, int]], frame_index: int
    ) -> List[Pose]:
        if frame is None or frame.size == 0 or not bboxes:
            return []

        if not self._runtime_available or self._session is None:
            # Model not present; keep pipeline alive without pose data.
            return []

        crops = []
        crop_boxes = []
        for bbox in bboxes:
            crop, cbox = self._preprocess(frame, bbox)
            crops.append(crop)
            crop_boxes.append((bbox, cbox))

        batch = np.concatenate(crops, axis=0)
        outputs = self._session.run([self._output_name], {self._input_name: batch})[0]

        # Expect shape (N, J, 2 or 3)
        poses: List[Pose] = []
        for i, (bbox, cbox) in enumerate(crop_boxes):
            raw_kp = outputs[i]
            norm_kp = self._normalize_output(raw_kp)
            # Pad/trim to num_joints
            if norm_kp.shape[0] < self.num_joints:
                pad = np.zeros((self.num_joints - norm_kp.shape[0], 2), dtype=np.float32)
                norm_kp = np.concatenate([norm_kp, pad], axis=0)
            norm_kp = norm_kp[: self.num_joints]
            joints_img = self._postprocess(norm_kp, cbox)
            poses.append(Pose(frame_index=frame_index, bbox=bbox, joints=joints_img))

        return poses
