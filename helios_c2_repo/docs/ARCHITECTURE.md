# Helios C2 Architecture

Helios C2 is organized as a small set of services wired together by an
orchestrator. This repo keeps everything in-process for clarity.

## Layers

1. Ingest Service
   - Reads scenario files or live adapters (in a real deployment)
   - Produces a list of `SensorReading` objects

2. Fusion Service
   - Groups sensor readings by time and location
   - Maintains a simple `EntityTrack` per logical actor
   - Emits provisional `Event` objects with severity and categories

3. Rules Engine
   - Applies declarative rules to enrich or generate events
   - Rules can raise severity, change categories, or suppress noise

4. Decision Service
   - Assigns priority and mission tags to events
   - Produces `TaskRecommendation` objects with rationale strings and approval metadata

5. Autonomy Service
   - Clusters tasks by domain and resource type
   - Creates abstract `TaskingPlan` objects for human approval

6. Export Service
   - Writes machine-readable JSON
   - Writes audit logs via the shared `AuditLogger`
   - Optional webhook emission for cloud/on-prem log sinks

Governance
- Applies policy filters across services: blocks domains/categories, caps severity by domain, and enforces forbidden actions before autonomy/export.
- Human-in-loop gating marks tasks pending when approval is required; approved tasks proceed to autonomy/export.
- Guardrails cap tasks per run by domain/event/total to prevent runaway autonomy outputs.

## Service Pattern

All services share a `ServiceContext` with:

- `config`: loaded YAML config
- `audit`: append-only audit logger
- `governance`: policy object that can block or downgrade actions

This mirrors the smaller incident-support pattern but generalizes it to
multi-domain scenarios.
