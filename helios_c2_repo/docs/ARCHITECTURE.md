# Helios C2 Architecture

Helios C2 is organized as a small set of services wired together by an
orchestrator. This repo keeps everything in-process for clarity so that
governance, approvals, guardrails, and audit are visible end-to-end in one
place. All “infrastructure actions” in this repo are simulated outputs; the
repo does not implement real device integrations.

This repo does not include integrations with real actuators; “infrastructure actions” are represented as records written to JSONL (and can optionally be forwarded over HTTP for demo/mocking).

The canonical wiring is implemented in [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py).

## Positioning

This repo is intentionally small and self-contained. It is not a full operational platform.

- Context and positioning vs mature platforms: [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md)
- What this repo focuses on advancing (grounded to code): [ADVANCING_SOA.md](ADVANCING_SOA.md)

## Technology status (what is implemented here)

Fully integrated and tested:

- Orchestrated pipeline wiring (ingest → fusion → rules → decision → oversight → export): [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py)
- Governance, approvals/RBAC, guardrails/risk budgets, audit: see the Governance section below and [OPERATIONS.md](OPERATIONS.md)
- Demo API/UI server: [src/helios_c2/http_api.py](../src/helios_c2/http_api.py) and [ui/index.html](../ui/index.html)

Integrated but best-effort / optional:

- Ontology graph (`graph.json`): [src/helios_c2/integrations/ontology_graph.py](../src/helios_c2/integrations/ontology_graph.py)
- Casebook (`casebook.json`): [src/helios_c2/integrations/casebook.py](../src/helios_c2/integrations/casebook.py)
- Entity profiles (`entity_profiles.json`): [src/helios_c2/integrations/entity_profiler.py](../src/helios_c2/integrations/entity_profiler.py)

Research prototypes (not fully wired into the core pipeline):

- Top-level folders “Entity Profiler”, “Investigative Support”, and “Vision Enhancement” include richer standalone code; the core pipeline uses the smaller, integration-focused modules under `src/helios_c2/integrations/`.

## Layers

0. Intent → Playbook (optional)
   - `IntentIngestService` reads commander intent from a JSONL file (or seeds demo intents from config).
   - `PlaybookMapper` maps intent text to structured `PlaybookAction` objects using config rules.
   - Outputs (when present): `out/intents.json`, `out/playbook_actions.json`.
   - These are inputs to downstream simulated platform command generation; they do not directly change governance/guardrail behavior.

1. Ingest Service
   - Reads scenario files (YAML) or polls JSONL (tail) in this reference repo.
    - Produces a list of `SensorReading` objects that normalize all incoming
       data into a common shape (id, domain, source_type, timestamp, geo,
       details).
    - Optional modules ingest: when `pipeline.ingest.mode` is `modules_media`,
       runs built-in media modules (vision/audio/thermal/gait/scene) on a
       configured media path and converts their outputs into `SensorReading`s so
       governance, approvals, guardrails, and audit still apply.

2. Fusion Service
    - Groups sensor readings by domain and track identifier (for example,
       logical actors, assets, or flows).
    - Maintains a simple `EntityTrack` per logical actor, updating last-seen
       timestamps.
    - Emits contextual information (tracks and per-domain counts) that the
       Rules Engine uses to generate `Event` objects.

3. Rules Engine
    - Applies declarative rules over `SensorReading` objects to generate
       `Event` objects.
    - Rules can raise severity, change categories, tag events, or suppress
       noise based on reading details (for example, flags, thresholds, or
       keywords).

4. Decision Service
    - Assigns priority and mission tags to open events using a configurable
       severity ordering.
    - Produces `TaskRecommendation` objects with rationale strings, confidence
       scores, and approval metadata (`requires_approval`, `status`, `approved_by`).
    - Applies RBAC-aware auto-approval using optional signed tokens, required
       roles, and minimum-approval counts.
    - Optionally derives infrastructure tasks (for example, lock/unlock/
       notify) from event categories and domains using `pipeline.infrastructure`
       mappings; these tasks still flow through governance and RBAC checks.

5. Autonomy Service
    - Clusters tasks by domain and resource type.
    - Applies autonomy modes (for example, suggest-only vs. limited auto-
       approval) while preserving human-on-the-loop oversight.
    - Prepares task groups for export to simulated infrastructure or external
       orchestration layers.

6. Export Service
    - Writes machine-readable JSON containing events, tasks, and pending tasks.
    - Optionally emits a STIX 2.1 bundle for interoperability with threat/
       incident-sharing tooling.
    - Optional webhook export posts full pipeline outputs to HTTP endpoints
       with retry and dead-letter-queue (DLQ) support.
    - Optional infrastructure export writes simulated gate/door/alert actions
       to JSONL and can optionally forward them via HTTP with its own DLQ.
    - Metrics export emits Prometheus text format for counters and timers
       collected in-process (for example, ingest, fusion, decision, export
       timing).

Governance
- Applies policy filters across services: blocks domains or categories,
   caps severity by domain, and enforces forbidden actions before autonomy/
   export.
- Human-in-the-loop gating marks tasks as pending when approval is required;
   approved tasks proceed to autonomy/export.
- Guardrails cap tasks per run by domain/event/total to prevent runaway task
   creation and automation outputs.
- Guardrails also support per-asset infrastructure caps and pattern-based
   caps for broad classes (for example, door_*), limiting how often
   infrastructure tasks may affect a given asset.
- Risk budgets hold back critical tasks per tenant with exponential backoff
   to reduce overload under noisy conditions.
- Guardrail health alerts emit audit entries when drop ratios exceed
   configured thresholds so overload can be detected during replay.
- RBAC roles and dual approvals allow role-based signer checks before
   automation proceeds, including per-action requirements from configuration.
- The audit trail uses hash chaining and optional signatures for tamper
   evidence and supports offline verification.
- Infrastructure tasks (open/close/lock/unlock/notify) are routed through the
   same governance, RBAC, and audit controls and are simulated only.

Platform Command Queue (simulated)
- After tasks are known, the orchestrator derives `PlatformCommand` objects from:
  - approved `TaskRecommendation`s
  - optional `PlaybookAction`s
- Commands are enqueued to a JSONL-backed in-memory queue and marked `sent` vs `deferred` based on configured `LinkState` availability.
- Outputs: `out/platform_commands.json`, plus the persistent queue file if configured.

Ontology Graph (best-effort)
- At the end of a run, Helios can write a lightweight relationship graph (`out/graph.json`) built from the exported artifacts.
- The demo API serves `GET /api/graph` and can also build the graph on-demand if missing.

## Service Pattern

All services share a `ServiceContext` with:

- `config`: loaded YAML config
- `audit`: append-only audit logger
- `governance`: policy object that can block or downgrade actions

Most services also use `metrics` to record counters/timers for export to Prometheus text format.

This mirrors the smaller incident-support pattern but generalizes it to
multi-domain scenarios.
