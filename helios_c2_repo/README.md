# Helios C2: Teaching Platform for Multi-Domain Coordination

Helios C2 is a **learning and prototyping tool** that shows how to coordinate responses across different operational areas (air, land, sea, space, cyber, and facilities). Think of it like a 911 dispatch system, but for multiple types of incidents happening at once.

**What it does**: Takes sensor alerts → groups related events → suggests actions → logs everything with strong audit trails.

**What it is NOT**: This is not a weapon system, not classified, and not for production use. It's a teaching tool with simulated scenarios.

**Key principle**: Humans always approve actions. The system suggests, humans decide.

## What You Get

This repository contains working code that demonstrates:

- **Data models** - How to structure sensor readings, events, and task recommendations
- **Five core services** - Ingest (collect alerts), Fusion (group related data), Decision (create tasks), Autonomy (prioritize), Export (output results)
- **Safety controls** - Approval workflows, audit logging, rate limits, and policy enforcement
- **Multi-format output** - JSON files, real-time webhooks, STIX 2.1 threat intelligence format

## How It Works

The system follows a simple pipeline:

1. **Ingest** - Reads sensor data from YAML scenario files or live JSONL feeds
2. **Fusion** - Groups related sensor readings by tracking ID and domain
3. **Rules** - Checks conditions (altitude violations, nighttime motion, etc.) and generates events
4. **Decision** - Creates task recommendations for each event
5. **Autonomy** - Organizes tasks by priority and domain
6. **Export** - Outputs events, tasks, and audit logs in multiple formats

**Human approval required**: Tasks can require domain-specific approvals before execution. The system tracks who approved what and when.

**Audit trail**: Every action generates a hash-chained audit entry that's tamper-evident (you can verify nothing was changed after the fact).

## Supported Domains

The system handles eight operational domains:
- **Air** - Drones, aircraft
- **Land** - Ground vehicles, personnel
- **Sea** - Surface vessels
- **Subsea** - Underwater operations
- **Space** - Satellites
- **Cyber** - Network events
- **Human** - Personnel tracking
- **Facility** - Buildings, gates, doors

## Quick Start

```bash
# Set up environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run a simulated scenario
python -m helios_c2.cli simulate --scenario examples/scenario_minimal.yaml --out out/
```

This command:
- Loads simulated sensor data from a YAML file
- Processes it through the five-stage pipeline
- Writes `events.json` (what happened) and `audit_log.jsonl` (who did what) to the `out/` folder

**Other ways to run it:**

Basic run with default config:
```bash
python -m helios_c2.cli run --config configs/default.yaml
```

Watch a live feed (reads new lines from a JSONL file as they appear):
```bash
python -m helios_c2.cli run --config configs/default.yaml --ingest-mode tail
```

## What's Actually Implemented

### Core Pipeline
- ✅ **Ingest service** - Reads YAML scenarios or polls JSONL files
- ✅ **Fusion service** - Groups sensor readings by entity and domain
- ✅ **Rules engine** - Evaluates conditions (altitude, time of day, keywords) and generates events
- ✅ **Decision service** - Creates task recommendations with rationale
- ✅ **Autonomy service** - Prioritizes and organizes tasks
- ✅ **Export service** - Outputs to JSON, JSONL, webhooks, or STIX 2.1 format

### Safety Controls (Really Implemented)
- ✅ **Human approval workflow** - Tasks can require approval before action; tracks who approved
- ✅ **Hash-chained audit log** - Tamper-evident logging with SHA-256 chains
- ✅ **RBAC (Role-Based Access Control)** - Approvers have secret keys; system verifies HMAC signatures
- ✅ **Rate limits** - Caps on tasks per domain/total/event to prevent runaway automation
- ✅ **Risk budgets** - Limits critical tasks per time window with exponential backoff
- ✅ **Policy enforcement** - Block entire domains, cap severity levels, forbid specific actions
- ✅ **Persistent risk tracking** - SQLite database tracks critical task counts across runs

### Integrations (Bonus Features)
- ✅ **Entity Profiler** - Tracks observations per entity, fuses biometric data, computes patterns
- ✅ **Vision Enhancement** - Frame stabilization, denoising, face detection/redaction, montage generation
- ✅ **Casebook** - Case/evidence/hypothesis tracking with classification markings
- ✅ **Ontology Graph** - Links events, tasks, and cases in a graph structure
- ✅ **Media Modules** - Process images/video/audio with detection, OCR, thermal analysis, gait recognition

### Export Formats
- ✅ JSON file (standard output)
- ✅ JSONL streams (for tasks and infrastructure actions)
- ✅ STIX 2.1 bundles (threat intelligence exchange format)
- ✅ Webhooks with retry/backoff/dead-letter queue
- ✅ Prometheus metrics format
- ✅ HTTP API (serves events, tasks, audit logs, and UI)

## What This Is NOT

- ❌ **Not a weapon system** - All scenarios are simulated; no actual control of weapons
- ❌ **Not classified** - Contains no classified capabilities or designs
- ❌ **Not production-ready** - This is a teaching tool, not a safety-critical system
- ❌ **Not a full C2 platform** - Simplified reference implementation for learning
- ❌ **Not connected to real sensors** - Uses file-based simulated data only

## Safety Controls Explained

**Human Approval** - You can configure the system so certain actions need a human to say "yes" before proceeding. The system tracks who approved each task and when.

**Audit Trail** - Every action writes a log entry that includes a hash of the previous entry. This creates a chain—if someone modifies an old entry, the chain breaks and you know something was tampered with.

**RBAC (Role-Based Access)** - Approvers get secret keys. When they approve something, the system checks a cryptographic signature (HMAC) to verify it's really them.

**Rate Limits** - Prevents the system from creating too many tasks at once. You can set limits per domain (e.g., max 10 air tasks), total (e.g., max 50 tasks), or per event.

**Risk Budgets** - Limits how many "critical" priority tasks can happen in a time window. If the system hits the limit, it slows down (exponential backoff) to prevent overload.

**Policy Blocks** - You can tell the system to completely ignore certain domains, cap the severity of events, or forbid specific actions.

## Docker Deployment

Run in a container (no cloud dependencies—works on Kubernetes, ECS, Docker, or bare metal):

```bash
docker build -t helios-c2 .
docker run --rm -v "$PWD/out:/app/out" helios-c2 \
   python -m helios_c2.cli simulate --scenario examples/scenario_minimal.yaml --out out
```

## Advanced Features

**Signed Approvals** - Auto-approve tasks with cryptographic tokens:
```bash
python -m helios_c2.cli simulate \
   --scenario examples/scenario_minimal.yaml \
   --out out/ \
   --policy-pack configs/policy_safety.yaml \
   --approver-id auto \
   --approver-token "$(python -c 'import hmac,hashlib,base64; print(base64.urlsafe_b64encode(hmac.new(b"changeme", b"ev:any:investigate:default", hashlib.sha256).digest()).decode().rstrip("="))')"
```

**STIX 2.1 Export** - Output threat intelligence in standard format:
```bash
# Add "stix" to pipeline.export.formats in your config
python -m helios_c2.cli simulate --scenario examples/scenario_minimal.yaml --out out/
# Generates out/events_stix.json
```

## Configuration Guide

Key settings you can change in YAML config files:

**Ingest Mode**
- `pipeline.ingest.mode: scenario` - Read from YAML scenario file (default)
- `pipeline.ingest.mode: tail` - Watch a JSONL file for new sensor readings

**Export Formats**
- `pipeline.export.formats: [json]` - Standard events.json output
- Add `task_jsonl` - Stream tasks to JSONL file
- Add `stix` - Generate STIX 2.1 threat intelligence bundles
- Add `infrastructure` - Output simulated gate/door/alert actions
- Add `stdout` - Print to console
- Add `webhook` - POST to HTTP endpoint

**Approval Requirements**
- `pipeline.human_loop.per_domain_approval` - Require approval per domain
- `pipeline.rbac.min_approvals` - How many approvers needed
- `pipeline.rbac.required_roles` - Which roles must approve (optional)

**Rate Limits**
- `pipeline.guardrails.rate_limits.per_domain` - Max tasks per domain
- `pipeline.guardrails.rate_limits.total` - Max total tasks
- `pipeline.guardrails.rate_limits.per_event` - Max tasks per event

**Risk Budgets**
- `pipeline.guardrails.risk_budgets` - Critical task limits with time windows
- `pipeline.guardrails.risk_store_path` - SQLite path for persistent tracking

**Policy Enforcement**
- `pipeline.governance.blocked_domains` - Ignore these domains entirely
- `pipeline.governance.severity_caps` - Max severity per domain
- `pipeline.governance.forbid_actions` - List of banned action types

## HTTP API

Start the web server to access events, tasks, and audit logs via HTTP:

```bash
python -m helios_c2.http_api --port 8000 --out-dir out/
```

**Available endpoints:**
- `GET /api/events` - Events and tasks from events.json
- `GET /api/tasks` - Tasks only
- `GET /api/audit` - Last N lines of audit log
- `GET /api/metrics` - Prometheus-format metrics
- `GET /api/config` - Current YAML configuration
- `GET /api/entity_profiles` - Entity tracking data
- `GET /api/graph` - Ontology graph (events/tasks/cases)
- `GET /api/casebook` - Case management data
- `POST /api/casebook` - Create new case/evidence/hypothesis
- `POST /api/enhance` - Submit video frame for enhancement
- Static files served from `ui/` directory

## Real-World Example

Here's what a complete scenario looks like:

1. **Sensor data comes in** - YAML file contains drone coordinates, ground vehicle positions, network scans
2. **Fusion groups them** - System tracks "Entity-AIR-001" (drone) and "Entity-LAND-002" (vehicle)
3. **Rules fire** - Detects "altitude_below 100m in restricted zone" → creates "airspace_violation" event
4. **Decision creates task** - "Investigate airspace violation, assign to air domain, priority=high"
5. **Approval check** - Air domain requires approval; task goes to "pending" status
6. **Human approves** - Operator signs with HMAC key; system verifies and marks approved
7. **Export** - Task written to JSONL, webhook POSTed to monitoring system, audit log updated
8. **Audit chain** - Every step logged with actor, timestamp, and hash link to previous entry

The output files in `out/` folder tell you:
- `events.json` - What happened (events) and what to do (tasks)
- `audit_log.jsonl` - Who did what and when (tamper-evident log)
- `metrics.prom` - Counts of events, tasks, approvals, rate-limit hits

## Learning Path

**Start here:**
1. Run `examples/scenario_minimal.yaml` to see the basic pipeline
2. Look at `out/events.json` to understand the data model
3. Check `out/audit_log.jsonl` to see the audit trail

**Then explore:**
1. Add approval requirements in `configs/default.yaml`
2. Set rate limits to see how guardrails work
3. Try different export formats (STIX, webhook, JSONL)
4. Configure policy blocks to forbid certain actions

**Advanced topics:**
1. Create custom scenario YAML files with your own sensor data
2. Use signed approvals with HMAC tokens
3. Set up persistent risk budgets with SQLite
4. Integrate with downstream tools via webhooks or STIX

## What You'll Learn

By studying and running this code, you'll understand:

- How to structure sensor → event → task pipelines
- Techniques for audit logging that's tamper-evident
- How to implement human approval workflows
- Rate limiting and risk budget patterns
- Multi-format export strategies (JSON, JSONL, webhooks, STIX)
- Policy enforcement and governance controls
- RBAC with cryptographic signatures

This is a **teaching platform**. The patterns here apply to real-world incident response, security operations, industrial control, and multi-team coordination systems.

---

**Repository**: Reference implementation for learning
**Status**: Active teaching tool, not production software
**License**: See LICENSE file
**Last Updated**: January 2026
