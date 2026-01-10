# Data Model

## Domains

Helios supports the following domains out of the box:

- air
- land
- sea
- subsea
- space
- cyber
- human
- facility

Domains are simple strings in this reference implementation.

## Core Types

### SensorReading

- `id`: string
- `sensor_id`: string
- `domain`: string
- `source_type`: e.g. "radar", "eo_ir", "radio", "log"
- `ts_ms`: integer UTC timestamp in ms
- `geo`: optional { lat, lon }
- `details`: free-form dict

### EntityTrack

- `id`: string
- `domain`: string
- `label`: short name
- `attributes`: dict
- `last_seen_ms`: integer

### Event

- `id`: string
- `category`: string (e.g. "threat", "safety", "intel", "status")
- `severity`: string ("info","notice","warning","critical")
- `status`: string ("open","acked","in_progress","resolved")
- `domain`: string or "multi"
- `summary`: human-readable text
- `time_window`: { start_ms, end_ms }
- `entities`: list of entity IDs
- `sources`: list of sensor IDs
- `tags`: list of strings
- `evidence`: list of objects with `{type, id/value, hash, observables}`

### TaskRecommendation

- `id`: string
- `event_id`: string
- `action`: string (e.g., "investigate","intercept","notify","lock","unlock","open","close","notify_emergency_services")
- `infrastructure_type`: optional string (e.g., "gate","door","emergency_channel")
- `asset_id`: optional string identifying the target asset
- `assignee_domain`: string
- `priority`: int (1 highest)
- `rationale`: human-readable text
- `confidence`: float 0..1
- `required_roles`: optional list of roles needed for approval (when configured per infra task)
- `min_approvals`: optional integer override for approvals on infra tasks
- `requires_approval`: bool
- `status`: string ("approved", "pending_approval", or "risk_hold")
- `approved_by`: optional string (may be comma-separated approver IDs)
- `evidence`: list of objects (e.g., event reference, observables)
- `tenant`: string
- `hold_reason`: optional string (e.g., risk budget hold)
- `hold_until_epoch`: optional float epoch seconds for backoff expiry

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
