from __future__ import annotations
import hashlib
import json
import orjson
import hmac
import base64
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    b = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    return sha256_bytes(b)


def pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def verify_hmac_token(message: str, token: str, secret: str) -> bool:
    if not secret or not token:
        return False
    mac = hmac.new(secret.encode("utf-8"), msg=message.encode("utf-8"), digestmod=hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(mac).decode("utf-8").rstrip("=")
    return hmac.compare_digest(expected, token)
