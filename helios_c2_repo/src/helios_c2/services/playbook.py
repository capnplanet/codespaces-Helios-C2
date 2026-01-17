from __future__ import annotations
from typing import Any, Dict, List

from .base import Service, ServiceContext
from ..types import CommanderIntent, PlaybookAction


class PlaybookMapper(Service):
    name = "playbook_mapper"
    version = "0.1"

    def run(self, intents: List[CommanderIntent], ctx: ServiceContext) -> List[PlaybookAction]:
        """
        Map CommanderIntent into structured PlaybookAction objects using config mappings.

        Config structure (example):
        pipeline:
          playbook:
            intents:
              - match:
                  contains: "echelon"
                action: echelon_left
                parameters:
                  formation: "echelon_left"
                  span_m: 500
        """
        mappings = ctx.config.get("pipeline", {}).get("playbook", {}).get("intents", [])
        actions: List[PlaybookAction] = []
        for intent in intents:
            matched = False
            text_lower = (intent.text or "").lower()
            for m in mappings:
                match_cfg = m.get("match", {})
                contains = match_cfg.get("contains")
                domain = match_cfg.get("domain")
                if contains and contains.lower() not in text_lower:
                    continue
                if domain and domain != intent.domain and domain != "multi":
                    continue
                action_name = m.get("action") or "investigate"
                params = dict(m.get("parameters") or {})
                params.setdefault("intent_text", intent.text)
                actions.append(
                    PlaybookAction(
                        id=f"pb_{intent.id}_{len(actions)}",
                        name=action_name,
                        parameters=params,
                        domain=intent.domain,
                        rationale=m.get("rationale"),
                        derived_from_intent=intent.id,
                    )
                )
                matched = True
                break
            if not matched:
                actions.append(
                    PlaybookAction(
                        id=f"pb_{intent.id}_fallback",
                        name="observe",
                        parameters={"intent_text": intent.text},
                        domain=intent.domain,
                        rationale="fallback: no mapping matched",
                        derived_from_intent=intent.id,
                    )
                )
        ctx.audit.write("playbook_map_done", {"actions": len(actions)})
        return actions
