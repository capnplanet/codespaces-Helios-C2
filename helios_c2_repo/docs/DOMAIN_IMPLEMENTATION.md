# Domain Implementation Reference

This document provides a comprehensive, code-grounded explanation of how Helios C2 handles operational domains (air, land, sea, subsea, space, cyber, human, and facility). All statements are directly referenced to actual code in the repository.

## Overview

Helios C2 supports eight operational domains as defined in `docs/DATA_MODEL.md` lines 5-14:
- **air** - Drones, aircraft
- **land** - Ground vehicles, personnel
- **sea** - Surface vessels
- **subsea** - Underwater operations
- **space** - Satellites
- **cyber** - Network events
- **human** - Personnel tracking
- **facility** - Buildings, gates, doors

These domains are implemented as string identifiers throughout the system, not as separate classes or modules.

**Note on Media Modules**: In addition to the eight operational domains above, the system also supports domain identifiers for media processing modules (vision, audio, thermal) when running in `modules_media` ingest mode (`configs/rules.sample.yaml` lines 84-117). These are treated the same way as operational domains but represent sensor types rather than operational areas.

## Domain Data Model

### Core Type Definition

Domains are represented as string fields in the core data types defined in `src/helios_c2/types.py`:

**SensorReading** (lines 7-14):
```python
@dataclass
class SensorReading:
    id: str
    sensor_id: str
    domain: str          # Domain identifier (e.g., "air", "land", "sea")
    source_type: str
    ts_ms: int
    geo: Optional[Dict[str, float]] = None
    details: Dict[str, Any] = field(default_factory=dict)
```

**EntityTrack** (lines 18-24):
```python
@dataclass
class EntityTrack:
    id: str
    domain: str          # Domain of the tracked entity
    label: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_seen_ms: int = 0
```

**Event** (lines 27-38):
```python
@dataclass
class Event:
    id: str
    category: str
    severity: str
    status: str
    domain: str          # Domain where event occurred (or "multi")
    summary: str
    time_window: Dict[str, int]
    entities: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
```

**TaskRecommendation** (lines 42-58):
```python
@dataclass
class TaskRecommendation:
    id: str
    event_id: str
    action: str
    assignee_domain: str  # Domain responsible for handling the task
    priority: int
    rationale: str
    confidence: float
    infrastructure_type: Optional[str] = None
    asset_id: Optional[str] = None
    requires_approval: bool = False
    status: str = "approved"
    approved_by: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tenant: str = "default"
    hold_reason: Optional[str] = None
    hold_until_epoch: Optional[float] = None
```

## Domain Processing Pipeline

### 1. Ingest Service

The IngestService (`src/helios_c2/services/ingest.py`) reads sensor data and creates SensorReading objects with domain identifiers.

**Example from scenario file** (`examples/scenario_minimal.yaml` lines 4-12):
```yaml
- id: "r1"
  sensor_id: "radar_alpha"
  domain: "air"              # Air domain sensor reading
  source_type: "radar"
  ts_ms: 1710000000000
  geo: { lat: 32.0, lon: -117.0 }
  details:
    altitude_ft: 300
    track_id: "air_001"
```

The service loads this data (lines 26-45 in `ingest.py`):
```python
def run(self, inp: Dict[str, Any], ctx: ServiceContext) -> List[SensorReading]:
    scenario_path = inp["scenario_path"]
    resolved = self._resolve_scenario_path(scenario_path)
    with open(resolved, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    
    readings: List[SensorReading] = []
    for item in raw.get("sensor_readings", []):
        readings.append(
            SensorReading(
                id=str(item["id"]),
                sensor_id=str(item["sensor_id"]),
                domain=str(item["domain"]),  # Domain extracted from YAML
                source_type=str(item["source_type"]),
                ts_ms=int(item["ts_ms"]),
                geo=item.get("geo"),
                details=item.get("details", {}),
            )
        )
    ctx.audit.write("ingest_done", {"count": len(readings), "scenario": str(resolved)})
    return readings
```

### 2. Fusion Service

The FusionService (`src/helios_c2/services/fusion.py`) groups sensor readings by domain and creates EntityTrack objects.

**Domain-based tracking** (lines 13-36):
```python
def run(self, readings: List[SensorReading], ctx: ServiceContext) -> Dict[str, any]:
    # Simple fusion: group by domain and track_id in details
    tracks: Dict[str, EntityTrack] = {}
    domain_counts = defaultdict(int)
    
    for r in readings:
        domain_counts[r.domain] += 1  # Count readings per domain
        track_id = r.details.get("track_id")
        if not track_id:
            track_id = f"anon_{r.domain}_{r.sensor_id}"  # Domain in anonymous ID
        if track_id not in tracks:
            tracks[track_id] = EntityTrack(
                id=track_id,
                domain=r.domain,        # Track assigned to reading's domain
                label=f"{r.domain}_track",
                attributes={},
                last_seen_ms=r.ts_ms,
            )
        else:
            tracks[track_id].last_seen_ms = max(tracks[track_id].last_seen_ms, r.ts_ms)
    
    # Audit log includes per-domain counts
    ctx.audit.write("fusion_done", {"tracks": len(tracks), "domains": dict(domain_counts)})
    return {"readings": readings, "tracks": tracks}
```

### 3. Rules Engine

The RulesEngine (`src/helios_c2/rules_engine.py`) applies domain-specific rules to sensor readings and generates Event objects.

**Domain filtering** (lines 29-34):
```python
def _matches(self, rule: Rule, reading: SensorReading) -> bool:
    cond = rule.when
    if cond.get("domain") and cond["domain"] != reading.domain:
        return False  # Rule only applies to specific domain
    if cond.get("source_type") and cond["source_type"] != reading.source_type:
        return False
    # ... additional condition checks
```

**Event creation with domain** (lines 57-81):
```python
def _make_event(self, rule: Rule, reading: SensorReading) -> Event:
    then = rule.then
    evidence_hash = sha256_json(reading.details or {})
    evidence = [
        {
            "type": "sensor_reading",
            "id": reading.id,
            "source": reading.sensor_id,
            "hash": evidence_hash,
            "observables": reading.details,
        }
    ]
    return Event(
        id=f"ev_{reading.id}_{rule.id}",
        category=then.get("category", "status"),
        severity=then.get("severity", "info"),
        status="open",
        domain=reading.domain,  # Event inherits domain from sensor reading
        summary=then.get("summary", "rule_triggered"),
        time_window={"start_ms": reading.ts_ms, "end_ms": reading.ts_ms},
        entities=[reading.details.get("track_id", "unknown")],
        sources=[reading.sensor_id],
        tags=[rule.id],
        evidence=evidence,
    )
```

### 4. Decision Service

The DecisionService (`src/helios_c2/services/decider.py`) creates TaskRecommendation objects and assigns them to appropriate domains.

**Domain assignment logic** (lines 39-48):
```python
for ev in events:
    if ev.status != "open":
        continue
    # Priority: invert severity number so higher severity -> lower priority value (1 is highest)
    sev_val = sev_order.get(ev.severity, 0)
    priority = max(1, 5 - sev_val)
    # Map domain to domain that should respond
    assignee = ev.domain if ev.domain != "multi" else "land"
    action = "investigate"
    rationale = f"{ev.summary} (severity={ev.severity}, domain={ev.domain})"
```

**Per-domain approval requirements** (lines 18-23):
```python
hl_cfg = ctx.config.get("pipeline", {}).get("human_loop", {})
default_require = bool(hl_cfg.get("default_require_approval", True))
domain_require = set(hl_cfg.get("domain_require_approval", []))  # Domains needing approval
auto_approve = bool(hl_cfg.get("auto_approve", True))
approver = hl_cfg.get("approver", "auto")
allow_unsigned = bool(hl_cfg.get("allow_unsigned_auto_approve", True))
```

**Checking if domain requires approval** (lines 51-54):
```python
requires_approval = assignee in domain_require or default_require
status = "approved"
approved_by = None
required_roles = set(required_roles_by_domain.get(assignee, []))
```

### 5. Autonomy Service

The AutonomyService (`src/helios_c2/services/autonomy.py`) clusters tasks by domain.

**Domain-based clustering** (lines 13-22):
```python
def run(self, tasks: List[TaskRecommendation], ctx: ServiceContext) -> Dict[str, any]:
    # Cluster tasks by assignee_domain and priority to form a simple "plan"
    by_domain = defaultdict(list)
    for t in tasks:
        by_domain[t.assignee_domain].append(  # Group by domain
            {"id": t.id, "event_id": t.event_id, "priority": t.priority}
        )
    plan = {"plans": dict(by_domain)}
    ctx.audit.write("autonomy_plan", {"domains": list(by_domain.keys())})
    return plan
```

## Domain-Specific Features

### Governance and Policy

Domains can be blocked entirely via configuration (`configs/default.yaml` lines 34-38):
```yaml
governance:
  forbid_actions: ["unauthorized_strike"]
  block_domains: []     # List of domains to completely ignore
  block_categories: []
  severity_caps: {}     # Max severity per domain
```

The governance module (`src/helios_c2/governance.py`) enforces these policies by filtering events and tasks based on their domain.

### Human Loop and Approvals

Per-domain approval requirements can be configured (`configs/default.yaml` lines 39-44):
```yaml
human_loop:
  default_require_approval: true
  domain_require_approval: []  # List of domains requiring approval
  auto_approve: true
  approver: "auto-approver"
  allow_unsigned_auto_approve: true
```

**Example requiring approval for specific domains** (`tests/test_guardrails.py` line 21):
```python
hl["domain_require_approval"] = ["facility", "air", "cyber", "human"]
```

### Rate Limits

Guardrails can limit the number of tasks per domain (`configs/default.yaml` lines 45-52):
```yaml
guardrails:
  rate_limits:
    per_domain: {}        # Map of domain -> max task count
    total: null           # Max total tasks across all domains
    per_event: null       # Max tasks per event
    per_asset_infra: {}
    per_asset_infra_patterns: []
```

**Example setting domain-specific limits**:
```yaml
rate_limits:
  per_domain:
    air: 10      # Max 10 tasks for air domain
    facility: 20 # Max 20 tasks for facility domain
```

### Infrastructure Mappings

Infrastructure tasks can be automatically created for specific domain/category combinations (`configs/default.yaml` lines 89-125):
```yaml
infrastructure:
  mappings:
    - match:
        category: "facility_intrusion"
        domain: "facility"              # Only applies to facility domain
      tasks:
        - action: "lock"
          asset_id: "gate_alpha"
          infrastructure_type: "gate"
          rationale: "Contain intrusion at perimeter"
          assignee_domain: "facility"  # Assigned to facility domain
```

## Domain Examples by Type

### Air Domain

**Sensor reading example** (`examples/scenario_minimal.yaml` lines 4-12):
```yaml
- id: "r1"
  sensor_id: "radar_alpha"
  domain: "air"
  source_type: "radar"
  ts_ms: 1710000000000
  geo: { lat: 32.0, lon: -117.0 }
  details:
    altitude_ft: 300
    track_id: "air_001"
```

**Air-specific rule** (from `configs/rules.sample.yaml`):
```yaml
- id: "altitude_violation"
  when:
    domain: "air"                    # Only applies to air domain
    condition: "altitude_below"
    threshold: 500
  then:
    category: "airspace_violation"
    severity: "warning"
    summary: "Aircraft below minimum altitude"
```

### Facility Domain

**Sensor reading example** (`examples/scenario_minimal.yaml` lines 14-22):
```yaml
- id: "r2"
  sensor_id: "cam_gate_1"
  domain: "facility"
  source_type: "camera"
  ts_ms: 1710000005000
  geo: { lat: 32.0, lon: -117.0 }
  details:
    night_motion: true
    track_id: "person_01"
```

**Facility-specific rule**:
```yaml
- id: "facility_intrusion"
  when:
    domain: "facility"
    condition: "night_motion"
  then:
    category: "facility_intrusion"
    severity: "warning"
    summary: "Unauthorized motion detected at night"
```

**Infrastructure integration** (`examples/scenario_infra.yaml` lines 4-12):
```yaml
- id: "g1"
  sensor_id: "gate_alpha_sensor"
  domain: "facility"
  source_type: "access_control"
  ts_ms: 1710000100000
  details:
    tailgating_detected: true
    track_id: "intruder_gate"
    zone: "north_perimeter"
```

### Cyber Domain

**Sensor reading example** (`examples/scenario_minimal.yaml` lines 24-31):
```yaml
- id: "r3"
  sensor_id: "net_s1"
  domain: "cyber"
  source_type: "netflow"
  ts_ms: 1710000010000
  details:
    scan_count: 25
    track_id: "ip_10_0_0_5"
```

**Cyber-specific rule**:
```yaml
- id: "port_scan_detected"
  when:
    domain: "cyber"
    condition: "port_scan"
    threshold: 20
  then:
    category: "threat"
    severity: "critical"
    summary: "Port scan activity detected"
```

### Human Domain

**Sensor reading example** (`examples/scenario_minimal.yaml` lines 33-40):
```yaml
- id: "r4"
  sensor_id: "radio_platoon"
  domain: "human"
  source_type: "radio"
  ts_ms: 1710000015000
  details:
    text: "Unit 3 this is Unit 1, mayday, we have casualties."
    track_id: "squad_3"
```

**Human-specific rule**:
```yaml
- id: "distress_call"
  when:
    domain: "human"
    condition: "keyword"
    threshold: "mayday"
  then:
    category: "safety"
    severity: "critical"
    summary: "Distress call received"
```

## Domain Testing

Domain functionality is tested throughout the test suite:

**Domain blocking test** (`tests/test_governance.py` lines 6-12):
```python
def test_block_domain(simulate, tmp_path):
    cfg = simulate.config
    cfg.setdefault("pipeline", {}).setdefault("governance", {})["block_domains"] = ["air"]
    result = simulate.run()
    # All air domain events should be blocked
    assert all(ev.domain != "air" for ev in result["events"])
```

**Per-domain approval test** (`tests/test_guardrails.py` line 21):
```python
hl["domain_require_approval"] = ["facility", "air", "cyber", "human"]
```

**Domain assignment verification** (`tests/test_stix_and_rbac.py` line 51):
```python
if t.assignee_domain == "air":
    # Verify air domain tasks
```

## Configuration Reference

### Default Domain

The system has a default domain for unspecified cases (`configs/default.yaml` line 3):
```yaml
helios:
  schema_version: "0.1"
  default_domain: "facility"
```

This is used in the HTTP API (`src/helios_c2/http_api.py` line 190):
```python
domain=str(payload.get("domain") or "facility"),
```

### Domain-Related Configuration Sections

1. **Governance** - Block or restrict specific domains
2. **Human Loop** - Per-domain approval requirements
3. **Guardrails** - Per-domain rate limits
4. **RBAC** - Per-domain role requirements
5. **Infrastructure** - Domain-specific infrastructure mappings

## Key Characteristics

### Domain as String Identifier

Domains are implemented as simple string values, not as classes or enums. This allows for flexibility and easy extension:

- Domains are compared using string equality
- No hard-coded domain validation (any string is accepted)
- Domain lists are defined in documentation and configuration
- The system gracefully handles unknown domains

### Domain Assignment Rules

1. **Sensor readings** - Domain assigned at data source
2. **Entity tracks** - Domain inherited from first sensor reading
3. **Events** - Domain inherited from sensor reading that triggered the rule
4. **Tasks** - Domain assigned based on event domain, with fallback to "land" for "multi" domain events

### Multi-Domain Support

Events can have domain "multi" for cross-domain scenarios. The decision service handles this (`src/helios_c2/services/decider.py` line 46):
```python
assignee = ev.domain if ev.domain != "multi" else "land"
```

This assigns multi-domain events to the "land" domain by default as a fallback.

## Summary

Helios C2's domain implementation is a simple, flexible string-based system that:

1. **Labels data** - Every sensor reading, track, event, and task carries a domain identifier
2. **Routes work** - Tasks are assigned to domains for handling
3. **Enforces policy** - Governance rules can block or restrict domains
4. **Controls approvals** - Human-in-the-loop can require per-domain approvals
5. **Manages resources** - Rate limits can be applied per domain
6. **Clusters operations** - Autonomy service groups tasks by domain for coordination

All domain handling is implemented through configuration and data flow, not through domain-specific code modules. This makes the system extensible and adaptable to different operational contexts without code changes.
