from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import time
import os
import orjson
import hmac
import hashlib

from .utils import sha256_bytes


@dataclass
class AuditEvent:
    ts_unix: float
    kind: str
    payload: Dict[str, Any]


class AuditLogger:
    def __init__(self, path: str, actor: str = "system", sign_secret: Optional[str] = None):
        self.path = path
        self.last_hash: Optional[str] = None
        self.actor = actor
        self.sign_secret = sign_secret
        self.seq = 0
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = orjson.loads(lines[-1])
                        self.last_hash = last_line.get("hash")
                        self.seq = int(last_line.get("seq", 0))
            except Exception:
                self.last_hash = None
                self.seq = 0

    def write(self, kind: str, payload: Dict[str, Any]) -> None:
        self.seq += 1
        evt = AuditEvent(ts_unix=time.time(), kind=kind, payload=payload)
        event_dict = asdict(evt)
        event_dict["actor"] = self.actor
        event_dict["seq"] = self.seq
        event_dict["prev_hash"] = self.last_hash
        serialized = orjson.dumps(event_dict, option=orjson.OPT_SORT_KEYS)
        current_hash = sha256_bytes(serialized)
        event_dict["hash"] = current_hash
        if self.sign_secret:
            sig = hmac.new(self.sign_secret.encode("utf-8"), msg=serialized, digestmod=hashlib.sha256).hexdigest()
            event_dict["sig"] = sig
        self.last_hash = current_hash
        line = orjson.dumps(event_dict).decode("utf-8")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
