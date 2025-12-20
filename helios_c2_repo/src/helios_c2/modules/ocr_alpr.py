from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def ocr_plates(path: Path, tracks):
    digest = sha256(str(path).encode("utf-8")).hexdigest()
    prefix = digest[:3].upper()
    number = int(digest[3:7], 16) % 10000
    return [
        {
            "track_id": t["track_id"],
            "plate": f"{prefix}-{number:04d}",
            "confidence": 0.73,
        }
        for t in tracks
    ]
