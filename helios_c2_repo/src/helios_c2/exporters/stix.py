from __future__ import annotations
import uuid
import datetime
from typing import List, Dict, Any

from ..types import Event, TaskRecommendation
from ..utils import sha256_json


def _ts(dt: datetime.datetime) -> str:
    return dt.replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def build_stix_bundle(events: List[Event], tasks: List[TaskRecommendation], cfg: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.datetime.now(datetime.timezone.utc)
    objs: List[Dict[str, Any]] = []

    for ev in events:
        obs = {
            "type": "observed-data",
            "spec_version": "2.1",
            "id": f"observed-data--{uuid.uuid4()}",
            "created": _ts(now),
            "modified": _ts(now),
            "first_observed": _ts(now),
            "last_observed": _ts(now),
            "number_observed": 1,
            "labels": [ev.category, ev.domain],
            "extensions": {
                "x-helios-event": {
                    "id": ev.id,
                    "severity": ev.severity,
                    "status": ev.status,
                    "summary": ev.summary,
                    "tags": ev.tags,
                    "entities": ev.entities,
                    "sources": ev.sources,
                    "evidence": ev.evidence,
                }
            },
        }
        objs.append(obs)

    for t in tasks:
        task_obj = {
            "type": "note",
            "spec_version": "2.1",
            "id": f"note--{uuid.uuid4()}",
            "created": _ts(now),
            "modified": _ts(now),
            "abstract": f"Task {t.action} for event {t.event_id}",
            "content": t.rationale,
            "object_refs": [],
            "labels": [t.assignee_domain, f"priority-{t.priority}", t.status],
            "extensions": {
                "x-helios-task": {
                    "id": t.id,
                    "event_id": t.event_id,
                    "action": t.action,
                    "assignee_domain": t.assignee_domain,
                    "priority": t.priority,
                    "confidence": t.confidence,
                    "requires_approval": t.requires_approval,
                    "status": t.status,
                    "approved_by": t.approved_by,
                    "evidence": t.evidence,
                    "tenant": t.tenant,
                    "hold_reason": t.hold_reason,
                    "hold_until_epoch": t.hold_until_epoch,
                }
            },
        }
        objs.append(task_obj)

    bundle = {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "spec_version": "2.1",
        "objects": objs,
        "x_helios_hash": sha256_json(objs),
    }
    return bundle
