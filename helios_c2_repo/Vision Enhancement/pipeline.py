from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import onnx
import onnx.helper as helper
import onnx.numpy_helper as numpy_helper
import onnxruntime as ort

from utils.hashing import deterministic_hash
from utils.provenance import file_hashes, runtime_metadata
from utils.redact import redact_faces
from utils.video import (
    blend_uncertainty,
    create_montage,
    read_video_frames,
    save_image,
    stabilize_frames,
    temporal_denoise,
    temporal_super_res,
    unsharp_mask,
    write_video_frames,
)


class EnhancementPipeline:
    def __init__(self, config: Dict, storage_dir: Path):
        self.config = config
        self.storage_dir = storage_dir
        np.random.seed(0)
        cv2.setRNGSeed(0)

    def run(self, video_path: str, request_id: str) -> Dict[str, str]:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        frames, fps = read_video_frames(video_path, deinterlace=self.config.get("deinterlace", False))
        if self.config.get("stabilize", True):
            frames, stab_report = stabilize_frames(frames)
        else:
            stab_report = {"residual_motion": 0.0}
        frames, denoise_report = temporal_denoise(frames, window=self.config.get("denose_window", 2))
        frames = unsharp_mask(frames, amount=self.config.get("sharpen_amount", 0.8))
        sr_frames, confidence = temporal_super_res(frames, scale=self.config.get("sr_scale", 2))
        conservative_frames = sr_frames
        uncertainty_map = None

        if self.config.get("ml_assisted", False):
            model_path = self.storage_dir / "sr_mini.onnx"
            ensure_sr_model(model_path, scale=self.config.get("sr_scale", 2))
            ml_frames = self._run_onnx_sr(frames, model_path, scale=self.config.get("sr_scale", 2))
            uncertainty_map = blend_uncertainty(conservative_frames[0], ml_frames[0])
            conservative_frames = ml_frames

        if self.config.get("redact_faces", False):
            conservative_frames = redact_faces(conservative_frames)

        enhanced_video = self.storage_dir / f"enhanced_{request_id}.mp4"
        montage_path = self.storage_dir / f"montage_{request_id}.jpg"
        metadata_path = self.storage_dir / f"metadata_{request_id}.yml"
        montage = create_montage(conservative_frames[: min(len(conservative_frames), 9)], cols=3)
        save_image(str(montage_path), montage)
        write_video_frames(conservative_frames, str(enhanced_video), fps)

        extras = {
            "stabilization": stab_report,
            "denoise": denoise_report,
            "sr_confidence_mean": float(np.mean(confidence)),
            "mode": self.config.get("mode", "conservative"),
            "ml_disclaimer": "ml_assisted produces hallucination risk" if self.config.get("ml_assisted", False) else "conservative deterministic pipeline",
        }

        input_hash = file_hashes({"input": video_path})
        metadata = runtime_metadata(self.config, inputs=input_hash)
        metadata = {**metadata, **extras}
        if uncertainty_map is not None:
            unc_path = self.storage_dir / f"uncertainty_{request_id}.png"
            save_image(str(unc_path), uncertainty_map)
            metadata["uncertainty_map"] = str(unc_path)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return {
            "video": str(enhanced_video),
            "montage": str(montage_path),
            "metadata": str(metadata_path),
        }

    def _run_onnx_sr(self, frames: List[np.ndarray], model_path: Path, scale: int) -> List[np.ndarray]:
        sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        output_frames: List[np.ndarray] = []
        for frame in frames:
            inp = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            inp = np.transpose(inp, (2, 0, 1))[None, ...]
            out = sess.run(None, {"input": inp})[0]
            out = np.clip(out[0], 0.0, 1.0)
            out = np.transpose(out, (1, 2, 0))
            out = cv2.cvtColor((out * 255.0).astype(np.uint8), cv2.COLOR_RGB2BGR)
            output_frames.append(out)
        return output_frames


def ensure_sr_model(path: Path, scale: int = 2) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    input_tensor = helper.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [1, 3, None, None])
    output_tensor = helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 3, None, None])

    scales = np.array([1.0, 1.0, float(scale), float(scale)], dtype=np.float32)
    scales_initializer = numpy_helper.from_array(scales, name="scales")
    resize_node = helper.make_node(
        "Resize",
        inputs=["input", "", "scales"],
        outputs=["output"],
        mode="linear",
        coordinate_transformation_mode="pytorch_half_pixel",
    )

    graph = helper.make_graph(
        nodes=[resize_node],
        name="sr_linear",
        inputs=[input_tensor],
        outputs=[output_tensor],
        initializer=[scales_initializer],
    )
    model = helper.make_model(graph, producer_name="deterministic_sr")
    onnx.checker.check_model(model)
    onnx.save(model, path)
