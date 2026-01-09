from __future__ import annotations

import mimetypes
from pathlib import Path


def guess_content_type(path: str | Path) -> str:
    ct, _ = mimetypes.guess_type(str(path))
    return ct or "application/octet-stream"
