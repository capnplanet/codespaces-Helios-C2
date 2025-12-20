from __future__ import annotations
import hashlib
import json
import orjson
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    b = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    return sha256_bytes(b)


def pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
