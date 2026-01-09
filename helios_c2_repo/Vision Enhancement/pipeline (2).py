from pathlib import Path
from typing import Dict, Optional

import yaml

from core.compliance.pipeline import CompliancePipeline
from core.enhancement.pipeline import EnhancementPipeline
from core.ocr.pipeline import OCRPipeline
from core.tracking.pipeline import TrackerPipeline


class FullPipeline:
    def __init__(self, base_dir: Path, configs: Dict[str, Dict]):
        self.base_dir = base_dir
        self.configs = configs

    def run(self, video_path: str, request_id: str) -> Dict[str, str]:
        enhance_dir = self.base_dir / "enhance"
        track_dir = self.base_dir / "track"
        ocr_dir = self.base_dir / "ocr"
        comp_dir = self.base_dir / "compliance"

        enhance = EnhancementPipeline(self.configs.get("enhance", {}), enhance_dir)
        enhanced = enhance.run(video_path, request_id)

        tracker = TrackerPipeline(self.configs.get("track", {}), track_dir)
        tracked = tracker.run(enhanced["video"], request_id)

        ocr = OCRPipeline(self.configs.get("ocr", {}), ocr_dir)
        ocr_result = ocr.run(enhanced["video"], request_id)

        compliance = CompliancePipeline(self.configs.get("policy", {}), comp_dir)
        comp_result = compliance.run(enhanced["video"], request_id)

        return {
            "enhanced": enhanced,
            "tracked": tracked,
            "ocr": ocr_result,
            "compliance": comp_result,
        }


def load_yaml(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
