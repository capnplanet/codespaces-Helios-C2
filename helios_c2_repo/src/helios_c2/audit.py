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
    def __init__(self, path: str, actor: str = "system", sign_secret: Optional[str] = None, verify_on_start: bool = False, require_signing: bool = False):
        self.path = path
        self.last_hash: Optional[str] = None
        self.actor = actor
        self.sign_secret = sign_secret
        self.require_signing = require_signing
        self.seq = 0
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = orjson.loads(lines[-1])
                        self.last_hash = last_line.get("hash")
                        self.seq = int(last_line.get("seq", 0))
                if verify_on_start:
                    self.verify_chain(raise_on_failure=True)
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
        event_dict["hash_alg"] = "sha256"
        event_dict["sig_alg"] = "hmac-sha256" if self.sign_secret else None
        serialized = orjson.dumps(event_dict, option=orjson.OPT_SORT_KEYS)
        current_hash = sha256_bytes(serialized)
        event_dict["hash"] = current_hash
        if self.sign_secret:
            sig = hmac.new(self.sign_secret.encode("utf-8"), msg=serialized, digestmod=hashlib.sha256).hexdigest()
            event_dict["sig"] = sig
        elif self.require_signing:
            raise RuntimeError("Audit signing required but no sign_secret provided")
        self.last_hash = current_hash
        line = orjson.dumps(event_dict).decode("utf-8")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def verify_chain(self, raise_on_failure: bool = False) -> bool:
        """Verify hash-chain (and signature if available) for the audit log."""
        if not os.path.exists(self.path):
            return True
        prev_hash = None
        expected_seq = 0
        try:
            with open(self.path, "rb") as f:
                for line in f:
                    data = orjson.loads(line)
                    expected_seq += 1
                    if data.get("seq") != expected_seq:
                        raise ValueError(f"Seq mismatch at {expected_seq}")
                    payload = dict(data)
                    payload.pop("hash", None)
                    sig = payload.pop("sig", None)
                    serialized = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
                    computed_hash = sha256_bytes(serialized)
                    if data.get("hash") != computed_hash:
                        raise ValueError(f"Hash mismatch at seq {expected_seq}")
                    if payload.get("prev_hash") != prev_hash:
                        raise ValueError(f"Prev hash mismatch at seq {expected_seq}")
                    if self.sign_secret and sig:
                        expected_sig = hmac.new(self.sign_secret.encode("utf-8"), msg=serialized, digestmod=hashlib.sha256).hexdigest()
                        if sig != expected_sig:
                            raise ValueError(f"Signature mismatch at seq {expected_seq}")
                    prev_hash = computed_hash
        except Exception as exc:
            if raise_on_failure:
                raise
            return False
        return True
