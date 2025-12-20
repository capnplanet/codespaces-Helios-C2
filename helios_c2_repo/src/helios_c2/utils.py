from __future__ import annotations
import hashlib
import json
import orjson
import hmac
import base64
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, ValidationError


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


_validator_cache: Dict[str, Draft202012Validator] = {}


def _schema_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas"


def get_validator(schema_name: str) -> Draft202012Validator:
    if schema_name in _validator_cache:
        return _validator_cache[schema_name]
    path = _schema_dir() / schema_name
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    validator = Draft202012Validator(raw)
    _validator_cache[schema_name] = validator
    return validator


def validate_json(schema_name: str, obj: Any) -> None:
    """Validate JSON object against a schema; raises ValidationError on failure."""
    validator = get_validator(schema_name)
    validator.validate(obj)
