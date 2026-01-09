from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Case:
    id: str
    title: str
    description: str
    status: str
    opened_at: float
    domain: str
    classification: str = "CUI"
    handling_caveats: List[str] = field(default_factory=list)


@dataclass
class Evidence:
    id: str
    kind: str
    description: str
    source: str
    created_at: float
    uri: Optional[str] = None
    case_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    classification: str = "CUI"
    handling_caveats: List[str] = field(default_factory=list)


@dataclass
class Hypothesis:
    id: str
    title: str
    description: str
    status: str
    confidence: float
    rationale: str
    created_at: float
    updated_at: float
    case_ids: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    classification: str = "CUI"
    handling_caveats: List[str] = field(default_factory=list)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def load_casebook(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"schema_version": "0.1", "cases": [], "evidence": [], "hypotheses": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_casebook(path: Path | str, payload: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def create_case(path: Path | str, *, title: str, description: str, domain: str, classification: str = "CUI") -> Dict[str, Any]:
    cb = load_casebook(path)
    now = time.time()
    case = Case(
        id=_new_id("case"),
        title=title,
        description=description,
        status="open",
        opened_at=now,
        domain=domain,
        classification=classification,
    )
    cb.setdefault("cases", []).append(asdict(case))
    save_casebook(path, cb)
    return asdict(case)


def add_evidence(
    path: Path | str,
    *,
    kind: str,
    description: str,
    source: str,
    uri: Optional[str] = None,
    case_ids: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    classification: str = "CUI",
) -> Dict[str, Any]:
    cb = load_casebook(path)
    now = time.time()
    ev = Evidence(
        id=_new_id("ev"),
        kind=kind,
        description=description,
        source=source,
        created_at=now,
        uri=uri,
        case_ids=list(case_ids or []),
        tags=list(tags or []),
        classification=classification,
    )
    cb.setdefault("evidence", []).append(asdict(ev))
    save_casebook(path, cb)
    return asdict(ev)


def create_hypothesis(
    path: Path | str,
    *,
    title: str,
    description: str,
    rationale: str,
    case_ids: Optional[List[str]] = None,
    evidence_ids: Optional[List[str]] = None,
    confidence: float = 0.0,
    classification: str = "CUI",
) -> Dict[str, Any]:
    cb = load_casebook(path)
    now = time.time()
    hyp = Hypothesis(
        id=_new_id("hyp"),
        title=title,
        description=description,
        status="open",
        confidence=float(confidence),
        rationale=rationale,
        created_at=now,
        updated_at=now,
        case_ids=list(case_ids or []),
        evidence_ids=list(evidence_ids or []),
        classification=classification,
    )
    cb.setdefault("hypotheses", []).append(asdict(hyp))
    save_casebook(path, cb)
    return asdict(hyp)
