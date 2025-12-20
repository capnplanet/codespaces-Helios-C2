from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SensorReading:
    id: str
    sensor_id: str
    domain: str
    source_type: str
    ts_ms: int
    geo: Optional[Dict[str, float]] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityTrack:
    id: str
    domain: str
    label: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_seen_ms: int = 0


@dataclass
class Event:
    id: str
    category: str
    severity: str
    status: str
    domain: str
    summary: str
    time_window: Dict[str, int]
    entities: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TaskRecommendation:
    id: str
    event_id: str
    action: str
    assignee_domain: str
    priority: int
    rationale: str
    confidence: float
    infrastructure_type: Optional[str] = None  # e.g., gate, door, emergency_channel
    asset_id: Optional[str] = None
    requires_approval: bool = False
    status: str = "approved"  # "approved" or "pending_approval"
    approved_by: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tenant: str = "default"
    hold_reason: Optional[str] = None
    hold_until_epoch: Optional[float] = None
