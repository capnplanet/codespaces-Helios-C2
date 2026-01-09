from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class Person(BaseModel):
    id: str
    name: Optional[str] = None
    identifiers: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None
    classification: str = "CUI"
    handling_caveats: List[str] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    title: str
    description: str
    status: str
    opened_date: str
    domain: str
    classification: str = "CUI"
    handling_caveats: List[str] = Field(default_factory=list)


class EvidenceBase(BaseModel):
    id: str
    kind: str
    description: str
    case_ids: List[str] = Field(default_factory=list)
    person_ids: List[str] = Field(default_factory=list)
    source: str
    created_at: str
    chain_of_custody: List[str] = Field(default_factory=list)
    classification: str = "CUI"
    handling_caveats: List[str] = Field(default_factory=list)


class DNAProfile(EvidenceBase):
    kind: Literal["DNAProfile"] = "DNAProfile"
    markers: Dict[str, str] = Field(default_factory=dict)
    quality_score: float = 0.0


class DigitalFingerprint(EvidenceBase):
    kind: Literal["DigitalFingerprint"] = "DigitalFingerprint"
    hashes: List[str] = Field(default_factory=list)
    device_ids: List[str] = Field(default_factory=list)
    accounts: List[str] = Field(default_factory=list)


class CCTVClip(EvidenceBase):
    kind: Literal["CCTVClip"] = "CCTVClip"
    uri: str
    camera_id: str
    start_ts: str
    end_ts: str
    location: Optional[Dict[str, float]] = None


class BodycamSegment(EvidenceBase):
    kind: Literal["BodycamSegment"] = "BodycamSegment"
    uri: str
    bodycam_id: str
    officer_id: str
    start_ts: str
    end_ts: str


class BehavioralDescriptor(EvidenceBase):
    kind: Literal["BehavioralDescriptor"] = "BehavioralDescriptor"
    mo_tags: List[str] = Field(default_factory=list)
    temporal_pattern: Optional[str] = None


class ReportExcerpt(EvidenceBase):
    kind: Literal["ReportExcerpt"] = "ReportExcerpt"
    text: str
    author: str
    report_id: str
    page: Optional[int] = None


class CrimeScene(EvidenceBase):
    kind: Literal["CrimeScene"] = "CrimeScene"
    location: Dict[str, float] = Field(default_factory=dict)
    scene_time: str


EvidenceUnion = DNAProfile | DigitalFingerprint | CCTVClip | BodycamSegment | BehavioralDescriptor | ReportExcerpt | CrimeScene


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    case_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    status: Literal["open", "supported", "rejected"] = "open"
    confidence: float = 0.0  # hypothesis-level confidence only
    rationale: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    created_by: str
    created_at: str
    updated_at: str
    classification: str = "CUI"
    handling_caveats: List[str] = Field(default_factory=list)


class CaseLinkScore(BaseModel):
    case_a: str
    case_b: str
    score: float
    explanation: str
    evidence_ids: List[str] = Field(default_factory=list)
    rule_ids: List[str] = Field(default_factory=list)


class CaseWorkflowState(BaseModel):
    case_id: str
    stage: Literal[
        "intake",
        "triage",
        "mitigation",
        "referral",
        "follow_up",
        "closure",
        "after_action",
    ] = "intake"
    owner: Optional[str] = None
    next_review: Optional[str] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    referral_destination: Optional[str] = None
