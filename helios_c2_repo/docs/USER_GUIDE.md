# Helios C2 User Guide

Helios C2 is a **simulation-focused reference implementation** of a multi-domain incident-support / C2-style pipeline.
It ingests synthetic sensor readings, fuses them into tracks/context, applies rules to generate events, produces task recommendations,
then enforces governance, approvals, guardrails, and auditability end-to-end.

This guide is focused on **how to run and use what’s in this repo**.

If you’re looking for context on how this repo fits alongside mature platforms, see:

- [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md)
- [ADVANCING_SOA.md](ADVANCING_SOA.md)
- [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)

## What you can do with this repo

- Run a synthetic scenario end-to-end and inspect:
  - generated events and tasks
  - pending approvals and risk holds
  - metrics, audit trail, and the investigation graph
- Run a lightweight API + UI server to explore outputs in a browser.
- Switch ingest modes:
  - `scenario` (YAML scenario file)
  - `tail` (JSONL file tail)
  - `modules_media` (runs built-in media modules and emits readings)
- Tune safety/oversight:
  - governance filters (block domains/categories, cap severity, forbid actions)
  - human-in-the-loop approvals and optional signed approvals (RBAC)
  - guardrails (rate limits + risk budgets)

## Repo layout (the parts you’ll touch)

- `configs/`
  - `default.yaml` — default pipeline configuration
  - `modules_media.yaml` — example config for media-module ingest
  - `policy_safety.yaml` — example policy pack (governance/human_loop/guardrails)
  - `rules.sample.yaml` — example ruleset
- `examples/`
  - `scenario_minimal.yaml` — batch scenario
  - `scenario_minimal.jsonl` — JSONL feed (for tail mode)
  - `scenario_infra.yaml` — scenario that maps into simulated infrastructure tasks
  - `sample_media.mp4` — sample media for `modules_media` mode
- `out/` (created at runtime)
  - `events.json`, `audit_log.jsonl`, `metrics.prom`, `graph.json`, etc.
- `ui/index.html` — single-file demo UI (no frontend framework)
- `src/helios_c2/http_api.py` — lightweight API + UI server (mostly stdlib; uses PyYAML/jsonschema)
- `src/helios_c2/cli.py` — CLI entrypoint (currently supports `simulate`)

## Installation

### Prerequisites

- Python >= 3.10

### Install dependencies

From the repo root:

```bash
pip install -r requirements.txt
```

### Make the `helios_c2` package importable

This repo uses a `src/` layout. You have two supported ways to run modules:

**Option A (recommended): editable install**

```bash
pip install -e .
```

**Option B: use `PYTHONPATH=src` when running commands**

```bash
PYTHONPATH=src python -m helios_c2.cli --help
```

If you see `ModuleNotFoundError: No module named 'helios_c2'`, you need one of the above.

## Quickstart: run a scenario and view the UI

### 1) Run a scenario

Generate outputs into `out/`:

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_minimal.yaml \
  --config configs/default.yaml \
  --out out
```

### 2) Start the API/UI server

This serves the UI and exposes `/api/*` endpoints that read from `out/`:

```bash
PYTHONPATH=src python -m helios_c2.http_api \
  --out out \
  --config configs/default.yaml \
  --ui-dir ui \
  --host 0.0.0.0 \
  --port 8080
```

Open:

- `http://localhost:8080`

## Using the UI

The UI is intentionally lightweight (single file) but it reads **real artifacts** produced by the pipeline.

### Demo Data mode vs Live mode

The UI includes a **Demo Data** toggle.

- **Demo Data: On** uses seeded demo data (useful for screenshots).
- **Demo Data: Off** uses live endpoints like `/api/events`, `/api/audit`, `/api/graph`, `/api/config`.

If something looks “disabled” or “missing” in Demo mode, switch Demo Data Off.

### Key pages and what they read

- **Dashboard**: shows metrics from `out/metrics.prom` (if enabled)
- **Events / Tasks**: reads `out/events.json`
- **Audit Trail**: reads and tails `out/audit_log.jsonl`
- **Modules**: reads `/api/config` and recent audit entries (e.g. `ingest_modules_done`)
- **Investigations → Graph**:
  - reads `/api/graph` (generated from `out/graph.json` or built best-effort)
  - includes:
    - a Browse search
    - a Query DSL panel (filter/traverse/path)
    - Nodes/Edges tables
    - a relational “Relational View” visualization (hover/click nodes)
    - a **node type filter** (chips) that filters both the visualization and tables

## Running different ingest modes

Ingest mode is set in config under:

- `pipeline.ingest.mode`

Supported values (see `src/helios_c2/orchestrator.py`):

### Mode: `scenario`

- Reads a YAML scenario via the ingest service.
- Best for quick, deterministic demo runs.

Example:

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_infra.yaml \
  --config configs/default.yaml \
  --out out
```

### Mode: `tail`

- Reads newline-delimited JSONL via `pipeline.ingest.tail.*`.
- In this reference implementation it’s still a “run” (collect up to `max_items`), not a long-lived daemon.

To try it, edit or copy config to set:

- `pipeline.ingest.mode: tail`
- `pipeline.ingest.tail.path: examples/scenario_minimal.jsonl`

### Mode: `modules_media`

- Runs media modules against a configured media path and converts outputs into `SensorReading`.
- Writes a module ingest audit entry (`ingest_modules_done`).
- Best-effort generates non-identifying entity profiles into `out/entity_profiles.json`.

Use the provided config:

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_minimal.yaml \
  --config configs/modules_media.yaml \
  --out out
```

Notes:

- In `modules_media` mode, the actual media path comes from `pipeline.ingest.media.path` in the config (the `--scenario` argument becomes a fallback).
- Modules are toggled by:
  - `pipeline.ingest.modules.enable_vision`
  - `pipeline.ingest.modules.enable_audio`
  - `pipeline.ingest.modules.enable_thermal`
  - `pipeline.ingest.modules.enable_gait`
  - `pipeline.ingest.modules.enable_scene`

## Outputs: what files get written

When you run the pipeline, outputs go under the `--out` directory.

Common artifacts:

- `events.json`
  - events, approved tasks, and pending tasks
- `audit_log.jsonl`
  - append-only audit trail of pipeline steps
  - entries are hash-chained and can be configured for verification/signing
- `metrics.prom` (if `pipeline.export.formats` includes `metrics`)
  - Prometheus text exposition
- `action_suggestion.json`
  - a simple cross-event/task suggestion produced at the end of the run
- `graph.json` (best-effort)
  - an ontology-style graph (events/tasks/casebook/evidence/entities)
- `entity_profiles.json` (best-effort; typically from `modules_media`)
  - non-identifying summaries derived from module outputs
- `risk_store.sqlite` (if configured)
  - persistent counters for risk budgets

## Configuration guide (where to look)

Your main lever is the YAML config, typically [configs/default.yaml](../configs/default.yaml).

To keep docs non-duplicative, detailed descriptions of:

- governance policy controls
- approvals/RBAC and signed tokens
- guardrails and risk budgets
- export formats and HTTP egress

live in [OPERATIONS.md](OPERATIONS.md).

Tip: you can merge the example safety pack into any run:

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_minimal.yaml \
  --config configs/default.yaml \
  --policy-pack configs/policy_safety.yaml \
  --out out
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'helios_c2'`

Use one of:

- `pip install -e .`
- `PYTHONPATH=src ...`

### UI loads but no events/metrics/audit

Ensure you ran a pipeline first and are pointing the API server at the same `--out` directory.

- Run: `PYTHONPATH=src python -m helios_c2.cli simulate ... --out out`
- Serve: `PYTHONPATH=src python -m helios_c2.http_api --out out ...`

Also check the UI toggle:

- Set **Demo Data: Off** to see live `/api/*`.

### `/api/graph` says graph not found

The API will try to build a graph from `out/` artifacts, but you’ll get a better graph once you have more artifacts:

- run a scenario (creates `events.json`)
- optionally create casebook items via the UI (writes `casebook.json`)
- optionally run `modules_media` (writes `entity_profiles.json`)

### Port already in use

If port 8080 is occupied, either:

- choose a different port: `--port 8081`
- stop the process using the port

## Where to go deeper

- Architecture walkthrough: [ARCHITECTURE.md](ARCHITECTURE.md)
- Type definitions: [DATA_MODEL.md](DATA_MODEL.md)
- Governance/approval/guardrail knobs: [OPERATIONS.md](OPERATIONS.md)
