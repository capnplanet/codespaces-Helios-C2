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
    route: List[Dict[str, Any]] = field(default_factory=list)
    link_hint: Optional[str] = None


# Commander intent expressed by a human in natural language or structured GUI input.
@dataclass
class CommanderIntent:
    id: str
    text: str  # Raw free-form statement (voice-to-text or typed)
    domain: str  # Primary domain or "multi"
    desired_effects: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    timing: Optional[str] = None  # e.g., "immediate", "phase-1", "by 1300Z"
    priority: Optional[str] = None  # e.g., "high", "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)


# Playbook-level action the system can map intent onto (e.g., formation, move, hold).
@dataclass
class PlaybookAction:
    id: str
    name: str  # e.g., "echelon_left", "move_sector", "hold_position"
    parameters: Dict[str, Any] = field(default_factory=dict)  # structured inputs like distances, bearings
    domain: str = "multi"
    rationale: Optional[str] = None
    derived_from_intent: Optional[str] = None  # CommanderIntent.id


# Platform-native command to send to a craft or pod.
@dataclass
class PlatformCommand:
    id: str
    target: str  # craft/pod identifier
    command: str  # platform-native verb
    args: Dict[str, Any] = field(default_factory=dict)
    phase: Optional[str] = None  # mission phase / timing marker
    priority: int = 3  # 1=highest
    status: str = "queued"  # queued, sent, acked, failed, deferred
    intent_id: Optional[str] = None
    playbook_action_id: Optional[str] = None
    link_window_required: bool = False  # indicates need for connectivity window
    metadata: Dict[str, Any] = field(default_factory=dict)
    asset_id: Optional[str] = None
    domain: Optional[str] = None
    route: List[Dict[str, Any]] = field(default_factory=list)
    link_state: Optional[Dict[str, Any]] = None


# Link/comms state snapshot to reason about degraded networks.
@dataclass
class LinkState:
    target: str  # craft/pod identifier
    available: bool
    last_check_epoch: float
    window_ends_epoch: Optional[float] = None
    notes: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Asset:
    """Lightweight platform asset representation (e.g., drone, rover)."""

    id: str
    domain: str
    vehicle_type: Optional[str] = None  # e.g., quadcopter, fixed_wing, rover
    platform_id: Optional[str] = None  # native platform ID if different from id
    label: Optional[str] = None
    status: str = "available"
    home_wp: Optional[Dict[str, float]] = None  # {lat, lon, alt?}
    loiter_alt_m: Optional[float] = None
    battery_pct: Optional[float] = None
    comm_link: Dict[str, Any] = field(default_factory=dict)  # {link: str, strength: float, window_ends_epoch: float}
    route: List[Dict[str, Any]] = field(default_factory=list)  # waypoints with optional ETA/alt
    link_state: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
