from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import json

from .base import Service, ServiceContext
from ..types import CommanderIntent


class IntentIngestService(Service):
    name = "intent_ingest"
    version = "0.1"

    def run(self, inp: Any, ctx: ServiceContext) -> List[CommanderIntent]:
        """
        Best-effort ingest of commander intent from config or a JSONL file.

        - If `inp` is a path, read JSONL lines with CommanderIntent-like dicts.
        - Otherwise, look for `pipeline.intent.seed_intents` in config for synthetic runs.
        """
        intents: List[CommanderIntent] = []
        path = None
        if isinstance(inp, str):
            path = Path(inp)
        if path and path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    intents.append(self._from_dict(raw))
                except Exception:
                    continue
        else:
            seeds = ctx.config.get("pipeline", {}).get("intent", {}).get("seed_intents", [])
            for raw in seeds:
                intents.append(self._from_dict(raw))

        ctx.audit.write("intent_ingest_done", {"intents": len(intents)})
        return intents

    def _from_dict(self, raw: Dict[str, Any]) -> CommanderIntent:
        return CommanderIntent(
            id=str(raw.get("id") or f"intent_{len(raw)}"),
            text=str(raw.get("text") or ""),
            domain=str(raw.get("domain") or "multi"),
            desired_effects=list(raw.get("desired_effects") or []),
            constraints=list(raw.get("constraints") or []),
            timing=raw.get("timing"),
            priority=raw.get("priority"),
            metadata=dict(raw.get("metadata") or {}),
        )
