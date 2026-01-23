# Helios C2: The Whole Platform (Feynman-Style)

This document explains Helios C2 like you’re a **smart 12-year-old**.

No math. No “ML model internals.” Just:

- what each major part does,
- what it reads and writes,
- and how all the parts work together.

Helios C2 is a **teaching / simulation** repo. It is not a production C2 platform, and the “actions” are **simulated**.

---

## 0) The shortest possible explanation

Imagine a **factory** that turns messy “sensor facts” into a clean “what should we do next?” recommendation.

- **Sensors** are like the factory’s input conveyor belt.
- The **pipeline services** are like machines on the belt.
- **Governance + approvals + guardrails** are the safety inspector.
- The **export step** writes results into a shared folder called `out/`.
- The **HTTP API** is a window that lets the UI read those `out/` files.
- The **UI** is the dashboard.
- **Investigations** tools (casebook + graph + entity profiles) are the detective’s notebook and corkboard.
- The **platform command queue** and **vehicle simulator** are a toy “robot side” that pretends to execute commands and emit telemetry.

---

## 1) The big picture map

The main “flow” is:

1) Get inputs (scenario YAML, file tail, media modules, telemetry)
2) Turn them into normalized `SensorReading` objects
3) Apply rules to create `Event` objects
4) Decide on `TaskRecommendation` objects
5) Apply oversight (policy + approvals + guardrails + risk budgets)
6) Optionally convert tasks/playbook actions into `PlatformCommand` objects
7) Export everything to `out/`
8) UI reads `out/` via `/api/*`

A simple sketch:

```
Inputs
  |  (scenario YAML / tail JSONL / media modules / telemetry)
  v
Ingest -> Fusion -> Rules -> Governance -> Decision -> Governance -> Guardrails/Risk -> Autonomy -> Export
  |                                                                                     |
  |                                                                                     +--> out/events.json + out/metrics.prom + out/audit_log.jsonl
  |
  +--> (optional) Entity Profiles (best-effort) -> out/entity_profiles.json

(optional) Intent -> Playbook ------------------------------+
                                                            |
                                                            v
                                               Platform Commands + Assets -> out/platform_commands.json + out/assets.json

(optional) Ontology Graph (best-effort) -> out/graph.json

UI  <--- HTTP API serves out/ artifacts (GET /api/*)
```

The canonical wiring for this is in `run_pipeline()` in `src/helios_c2/orchestrator.py`.

---

## 2) The shared memory: the `out/` folder

In this repo, a lot of “integration” is very simple:

- services run in-process, AND
- key results are written to disk in `out/`, AND
- the demo API serves those artifacts to the UI.

Think of `out/` like a shared bulletin board.

Common artifacts:

- `out/events.json`
  - the main export: events, approved tasks, pending tasks

- `out/audit_log.jsonl`
  - an append-only timeline of what happened (hash-chained, optionally signed)

- `out/metrics.prom`
  - counters/timers in Prometheus text format

Optional artifacts (appear depending on config and ingest mode):

- `out/intents.json`, `out/intents.jsonl`
  - commander intent, either “snapshotted” or streamed

- `out/playbook_actions.json`
  - intent mapped into more structured actions

- `out/action_suggestion.json`
  - a single “what should we do next?” suggestion for the UI

- `out/platform_commands.json`
  - simulated platform commands derived from approved tasks and/or playbook actions

- `out/assets.json`
  - simulated platform asset list (with route/link/status)

- `out/entity_profiles.json`
  - best-effort, non-identifying entity summaries derived from media-module outputs

- `out/casebook.json`
  - operator-authored cases/evidence/hypotheses

- `out/graph.json`
  - a best-effort relationship graph built from the other artifacts

---

## 3) “Services” (the pipeline machines) and what each one does

In Helios, a **service** is a small class that takes some input + a shared context (`config`, `audit`, `governance`, `metrics`) and returns outputs.

### 3.1 Orchestrator (the conductor)

- **Where:** `src/helios_c2/orchestrator.py`
- **Job:** runs services in the right order, collects outputs, writes artifacts.

If you only remember one thing, remember this:

> The orchestrator is the glue that turns “a bunch of parts” into “one pipeline run.”

### 3.2 Intent ingest (optional): “what the commander wants”

- **Where:** `src/helios_c2/services/intent.py`
- **Job:** read commander intent from a configured JSONL path (or seed demo intent).

Output:
- list of `CommanderIntent` objects
- exported to `out/intents.json` (snapshot) and/or appended to `out/intents.jsonl` (stream)

How it connects:
- intent is *not* an event by itself
- it is used to create playbook actions (next step) and platform commands

### 3.3 Playbook mapper (optional): “turn intent into structured actions”

- **Where:** `src/helios_c2/services/playbook.py`
- **Job:** map free-text intent into structured `PlaybookAction` objects.

Output:
- `out/playbook_actions.json`

How it connects:
- playbook actions can become simulated platform commands

### 3.4 Ingest: “read inputs and normalize them”

- **Where:** `src/helios_c2/services/ingest.py`
- **Job:** produce a list of normalized `SensorReading` objects.

Helios supports multiple ingest modes:

1) **Scenario ingest** (default)
   - reads a scenario YAML file with `sensor_readings`

2) **Tail ingest**
   - reads a JSONL file repeatedly (like “follow the log”)

3) **Media-modules ingest**
   - runs built-in modules (vision/audio/thermal/etc.) over media
   - converts those outputs into `SensorReading` objects
   - **Where:** `src/helios_c2/adapters/media_modules.py`

Also:
- telemetry readings can be added from a telemetry JSONL path (so the pipeline can “see” vehicle status updates)

### 3.5 Fusion: “group readings into simple tracks”

- **Where:** `src/helios_c2/services/fusion.py`
- **Job:** group readings by `domain` and (best-effort) `track_id` so downstream stages can reason about “entities over time.”

Output:
- a list of readings (unchanged)
- a dictionary of `EntityTrack` objects (simple track summaries)

### 3.6 Rules engine: “if this, then that”

- **Where:** `src/helios_c2/rules_engine.py`
- **Job:** take `SensorReading` objects and generate `Event` objects when rules match.

Rules are configured in YAML and implement simple conditions like:
- thresholds (e.g., altitude below X)
- boolean flags
- keyword matches
- simple detail equality checks

Output:
- “raw” events (before policy filtering)

### 3.7 Governance (policy): “is this even allowed?”

- **Where:** `src/helios_c2/governance.py`
- **Job:** act like a safety inspector that can:
  - block whole domains
  - block event categories
  - cap severity by domain
  - forbid certain actions entirely

This happens in multiple places:
- events are filtered/capped after rules
- tasks are filtered/blocked after decision

### 3.8 Decision service: “what tasks should we do?”

- **Where:** `src/helios_c2/services/decider.py`
- **Job:** turn events into `TaskRecommendation` objects.

Key behaviors:
- assigns priority from severity (critical events become high-priority tasks)
- determines whether a task requires approval
- supports a demo RBAC-style approval mechanism (HMAC tokens) and minimum-approval counts
- can also generate **infrastructure tasks** (lock/unlock/notify/etc.) from event category/domain mappings

Output:
- a list of tasks, each marked as:
  - `approved`, or
  - `pending_approval`

### 3.9 Guardrails + risk budgets: “don’t stampede”

- **Where:** `src/helios_c2/orchestrator.py` (guardrails + risk budget functions)
- **Job:** prevent runaway automation.

Guardrails can cap:
- total tasks per run
- tasks per domain
- tasks per event
- infrastructure tasks per asset (including wildcard patterns)

Risk budgets can:
- temporarily hold back “critical” tasks per tenant with exponential backoff
- store counters in SQLite via `src/helios_c2/risk_store.py` (optional)

Output:
- tasks can become `risk_hold` instead of fully approved

### 3.10 Autonomy service: “group tasks into a plan”

- **Where:** `src/helios_c2/services/autonomy.py`
- **Job:** cluster approved tasks into a lightweight “plan” (mostly for audit/demo readability).

### 3.11 Export service: “write the results down”

- **Where:** `src/helios_c2/services/exporter.py`
- **Job:** write outputs to disk (and optionally to other formats).

Exports include:
- `events.json` (the main payload)
- optional JSONL streams
- optional simulated infrastructure actions JSONL
- optional STIX bundle
- optional webhook POST (best-effort)
- optional metrics file

---

## 4) The oversight + accountability parts (why this isn’t just “automation”)

### 4.1 Audit trail: “a tamper-evident diary”

- **Where:** `src/helios_c2/audit.py`
- **What it is:** a JSONL log where each line includes the hash of the previous line.

That means:
- if someone changes the past, the chain breaks
- you can verify the chain later
- it can optionally include HMAC signatures

### 4.2 Metrics: “how fast and how much”

- **Where:** `src/helios_c2/metrics.py`
- **What it does:** counts things (events, drops, exports) and times stages (ingest, fusion, decision, …)

---

## 5) The investigations helpers (the detective tools)

These are “optional helpers” that reuse the same exported artifacts.

### 5.1 Casebook (operator notes)

- **Where:** `src/helios_c2/integrations/casebook.py`
- **File:** `out/casebook.json`
- **What it does:** lets an operator create:
  - cases
  - evidence items
  - hypotheses

### 5.2 Entity profiles (best-effort, non-identifying)

- **Where:** `src/helios_c2/integrations/entity_profiler.py`
- **File:** `out/entity_profiles.json`
- **What it does:** builds summaries of observed tracks over time.

Important detail:
- it works best when the media ingest produces gait embeddings
- otherwise it falls back to lightweight per-frame observations

### 5.3 Ontology graph (the corkboard)

- **Where:** `src/helios_c2/integrations/ontology_graph.py`
- **File:** `out/graph.json`
- **What it does:** merges artifacts into a single graph of nodes and edges.

It can include:
- events + tasks
- pending tasks
- platform commands + assets
- casebook items
- entity profiles

It is **best-effort** (missing inputs should not break the pipeline).

---

## 6) “Platform orchestration” (the toy robot side)

Helios includes a simulated loop that looks like:

1) Helios produces `PlatformCommand` objects
2) commands are queued/sent/deferred based on comms availability
3) a simulated vehicle backend emits telemetry
4) telemetry can be ingested back into Helios

### 6.1 Platform assets and link states

- **Where:** assets/link state assembly lives in `src/helios_c2/orchestrator.py`
- **Files:** `out/assets.json`

Assets are a UI-friendly “status card” for each platform:
- domain (air/land/etc.)
- route
- battery
- comm link
- link availability window

### 6.2 Platform command queue (send vs deferred)

- **Where:** `src/helios_c2/adapters/platform_link.py`

The queue simulates degraded comms:
- if a target’s `LinkState.available` is true, a command can be marked `sent`
- otherwise it is marked `deferred` and kept in the queue

Exports:
- `out/platform_commands.json`

### 6.3 Vehicle backend simulator (telemetry generator)

- **Where:** `src/helios_c2/simulators/vehicle_backend.py`

What it does:
- reads `out/platform_commands.json`
- updates a toy vehicle state (“moving”, “holding”, etc.)
- periodically writes telemetry readings into a JSONL file
- also writes refreshed `out/assets.json`

This lets you demo a loop where “commands → movement → telemetry → updated asset cards.”

---

## 7) The HTTP API + UI (how humans interact with the artifacts)

### 7.1 HTTP API

- **Where:** `src/helios_c2/http_api.py`
- **What it does:** serves:
  - static UI files (default `ui/`)
  - JSON endpoints that read/write files in `out/`

Common GET endpoints:
- `/api/events`, `/api/tasks`, `/api/audit`, `/api/metrics`, `/api/config`
- `/api/intents`, `/api/playbook_actions`
- `/api/assets`, `/api/platform_commands`
- `/api/entity_profiles`, `/api/casebook`, `/api/graph`

Common POST endpoints:
- `/api/intents` (append a new intent to the stream)
- `/api/platform_commands` (add a command)
- `/api/telemetry` (inject telemetry readings)
- `/api/casebook` (create cases/evidence/hypotheses)
- `/api/action_suggestion` (approve/deny the current suggested action)

### 7.2 UI

- **Where:** `ui/index.html`
- **What it does:** reads the `/api/*` endpoints and turns them into:
  - Sensors views
  - Investigations views
  - platform asset and command dashboards
  - intent/voice-command demos

The UI is intentionally a single-file demo to keep the “end-to-end story” easy to learn.

---

## 8) A complete story (end-to-end example)

Here’s the “movie” the platform is trying to demonstrate:

1) You run a scenario (or ingest from media modules)
2) Rules generate events
3) Decision proposes tasks
4) Governance/approvals decide what’s allowed now vs pending
5) Guardrails/risk budgets prevent overload
6) Export writes everything to `out/`
7) UI shows you events/tasks/audit/metrics
8) You add investigation notes (casebook), view entity profiles, or explore the graph
9) Optional: you add intent (“Search sector A”), map to playbook actions, and see platform commands
10) Optional: vehicle backend simulates moving and produces telemetry that changes asset status

---

## 9) Where to look next

- If you want the exact pipeline order and responsibilities: see `docs/ARCHITECTURE.md`.
- If you want how the Sensors + Investigations UI pages are implemented: see `docs/SENSORS_AND_INVESTIGATIONS_FEYNMAN.md`.
- If you want the type definitions and what’s inside each artifact: see `docs/DATA_MODEL.md`.
