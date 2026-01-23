# Data Model

This repo uses plain Python dataclasses in [src/helios_c2/types.py](../src/helios_c2/types.py).
Schemas for the main exports live under `schemas/`.

## Domains

Domains are simple strings. The example scenarios and configs primarily use:

- `air`, `land`, `sea`, `subsea`, `space`, `cyber`, `human`, `facility`

In `modules_media` ingest mode, module-produced readings commonly use domains like:

- `vision`, `audio`, `thermal`, `scene`

Nothing in the pipeline enforces a fixed domain enum; governance/approvals/guardrails operate on whatever domain strings appear.

## Core Types

### SensorReading

- `id`: string
- `sensor_id`: string
- `domain`: string
- `source_type`: string
- `ts_ms`: integer UTC timestamp in ms
- `geo`: optional `{lat, lon}`
- `details`: free-form object

### EntityTrack

- `id`: string
- `domain`: string
- `label`: string
- `attributes`: object
- `last_seen_ms`: integer

### Event

- `id`: string
- `category`: string
- `severity`: string (commonly `info|notice|warning|critical`)
- `status`: string (commonly `open|acked|in_progress|resolved`)
- `domain`: string
- `summary`: string
- `time_window`: `{start_ms, end_ms}`
- `entities`: list of strings
- `sources`: list of strings
- `tags`: list of strings
- `evidence`: list of objects

### TaskRecommendation

- `id`: string
- `event_id`: string
- `action`: string (e.g., `investigate`, `lock`, `unlock`, `notify_emergency_services`)
- `assignee_domain`: string
- `priority`: int (1 is highest)
- `rationale`: string
- `confidence`: float
- `infrastructure_type`: optional string (e.g., `gate`, `door`, `emergency_channel`)
- `asset_id`: optional string
- `requires_approval`: bool
- `status`: string (`approved`, `pending_approval`, `risk_hold`)
- `approved_by`: optional string
- `evidence`: list of objects
- `tenant`: string
- `hold_reason`: optional string
- `hold_until_epoch`: optional float epoch seconds
- `route`: list of waypoints/objects (optional; used when creating platform commands)
- `link_hint`: optional string

Approval requirements such as “required roles” and “minimum approvals” are configured in `pipeline.rbac.*` and `pipeline.infrastructure.*` and affect whether tasks become `approved` or `pending_approval`.

## Optional Planning / Platform Types

These are used to model “commander intent → playbook actions → platform commands” in a fully simulated way.

### CommanderIntent

- `id`, `text`, `domain`
- `desired_effects`, `constraints`
- `timing`, `priority`
- `metadata`

### PlaybookAction

- `id`, `name`, `domain`
- `parameters`: object
- `rationale`, `derived_from_intent`

### PlatformCommand

- `id`, `target`, `command`, `args`
- `phase`, `priority`, `status`
- `intent_id`, `playbook_action_id`
- `link_window_required`
- `metadata`, `asset_id`, `domain`, `route`, `link_state`

### Asset

Lightweight view of a platform asset for the UI.

### LinkState

Connectivity snapshot used to simulate “send vs deferred” behavior.

## Ontology Graph (graph.json)

Helios emits a best-effort **relationship graph** as `out/graph.json` (also served via `/api/graph`).

This is a lightweight “ontology-like” representation intended for investigations and UI exploration; it is not a full enterprise ontology management system.

### Graph Payload

- `schema_version`: string (currently `"0.1"`)
- `generated_at`: ISO timestamp
- `nodes`: list of node objects
- `edges`: list of edge objects
- `stats`: summary counts and the set of observed `node_types` / `edge_types`

### GraphNode

- `id`: string (namespaced, e.g. `event:...`, `case:...`, `entity:...`)
- `type`: string (e.g. `event`, `task`, `task_pending`, `case`, `hypothesis`, `evidence`, `entity`, `track`, `camera`, `source`)
- `label`: string (human-friendly)
- `props`: object (free-form key/value map)

### GraphEdge

- `source`: node id string
- `target`: node id string
- `type`: string (relationship type)
- `props`: object (free-form)

Common edge types include `MENTIONS`, `DERIVED_FROM`, `SUPPORTED_BY`, `RESPONDS_TO`, `EVIDENCE_FOR`, `HYPOTHESIS_FOR`, `TRACKED_AS`, `OBSERVED_BY`.

## Primary On-Disk Artifacts

The pipeline writes artifacts into the selected output directory (commonly `out/`). Common files include:

- `events.json`, `audit_log.jsonl`, `metrics.prom`
- Optional: `events_stix.json`, `tasks.jsonl`, `infrastructure_actions.jsonl`
- Optional: `intents.json`, `playbook_actions.json`, `platform_commands.json`, `assets.json`
- Optional/best-effort: `graph.json`, `entity_profiles.json`, `casebook.json`

## Graph Query DSL (UI)

The Investigations → Graph UI includes a small query/filter DSL to explore the graph.

### Statements

- `nodes where <expr>`: select nodes and return the induced subgraph.
- `edges where <expr>`: select edges and return their endpoint nodes.
- `neighbors where <node-expr> depth <n> dir (in|out|both) edge where <edge-expr>`: expand a neighborhood.
- `path from <node-expr> to <node-expr> max <n> dir (in|out|both) edge where <edge-expr>`: shortest-path search.

### Expressions

- Boolean: `and`, `or`, `not`, parentheses.
- Comparators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `~` (substring contains), `in (a,b,c)`.

### Fields

- Node fields: `id`, `type`, `label`, `props.<key>`
- Edge fields: `source`, `target`, `type`, `props.<key>`

### Examples

- `nodes where type=event and props.severity=critical`
- `neighbors where type=event depth 2 dir both`
- `path from type=task to type=case max 6 dir both`
