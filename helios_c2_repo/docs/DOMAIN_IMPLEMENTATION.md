# Domain Implementation (Concise)

Domains in Helios C2 are **string identifiers** carried through the pipeline.
They show up in `SensorReading.domain`, `Event.domain`, and `TaskRecommendation.assignee_domain`.

This doc is intentionally short to avoid duplicating [docs/ARCHITECTURE.md](ARCHITECTURE.md) and [docs/DATA_MODEL.md](DATA_MODEL.md).

## Domain Vocabulary Used In This Repo

The examples primarily use operational domains:

- `air`, `land`, `sea`, `subsea`, `space`, `cyber`, `human`, `facility`

In `modules_media` ingest mode the pipeline may also produce readings under sensor/module-oriented domains:

- `vision`, `audio`, `thermal`, `scene`

All of these are treated uniformly by governance/approvals/guardrails because they are just strings.

## Where Domains Matter

### 1) Rules applicability

Rules can match on domain and source type. In practice this means you can keep “facility intrusion” rules from firing on `cyber` log events, and vice-versa.

### 2) Governance policy

Governance can:

- drop events by `pipeline.governance.block_domains`
- drop events by `pipeline.governance.block_categories`
- cap event severity per domain via `pipeline.governance.severity_caps`
- forbid task actions globally via `pipeline.governance.forbid_actions`

### 3) Approvals (human loop + RBAC)

Approvals are configured in two layers:

- `pipeline.human_loop.*` determines whether a task *requires* approval.
- `pipeline.rbac.*` determines whether a task can be *approved* via signed tokens (and/or allowed unsigned auto-approval).

Domains matter because approval requirements can be applied per domain (`pipeline.human_loop.domain_require_approval`) and roles can be required per domain (`pipeline.rbac.required_roles`).

### 4) Guardrails and risk budgets

Guardrails can cap tasks per domain for a run via `pipeline.guardrails.rate_limits.per_domain`.

Risk budgets are per tenant (not per domain) but still commonly correlate with domain-heavy scenarios.

### 5) Exports and “simulated actuation”

Tasks that include an `infrastructure_type` are considered “infrastructure tasks” and can be exported separately.
These are simulated outputs only.

## If You Need Details

- Data shapes: [docs/DATA_MODEL.md](DATA_MODEL.md)
- Pipeline flow: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Config knobs: [docs/OPERATIONS.md](OPERATIONS.md)
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
