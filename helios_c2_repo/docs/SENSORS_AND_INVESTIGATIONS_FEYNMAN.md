# Sensors ↔ Investigations Interaction (Feynman-Style)

This document explains, in plain language, how Helios C2’s **Sensors** interface and **Investigations** interface interact.

The goal is not to “explain every ML model,” but to explain **how information moves** from:

1) sensor/config choices →
2) pipeline outputs written into `out/` →
3) API endpoints that serve those outputs →
4) UI elements that render them →
5) investigations (casebook + graph) that *reuse* the same outputs.

It also includes a function-by-function walkthrough of the UI logic that implements these pages.

---

## 1) The simplest mental model

Imagine Helios as a small factory:

- **Sensors page** is the **factory control panel**.
  - It answers: “What machines are enabled?” and “What did they produce in the last run?”

- **Investigations page** is the **investigator’s notebook + corkboard**.
  - It answers: “What does the system know?” and “How do I organize evidence into a case?”

**Key point:** the Sensors UI and Investigations UI do *not* talk to each other directly.

They “interact” through shared **artifacts** and shared **API endpoints**:

- the pipeline writes to `out/` (e.g. `events.json`, `entity_profiles.json`, `graph.json`, `audit_log.jsonl`)
- the demo server exposes them via `/api/*`
- the UI reads them and renders them

So the interaction looks like:

> Sensors choices → pipeline run → out artifacts → Investigations views

---

## 2) The shared backbone: artifacts + endpoints

### 2.1 Output artifacts (the “truth on disk”)

Helios uses the `out/` directory as the system’s shared memory.

Common files that matter for Sensors + Investigations:

- `out/events.json`
  - events and tasks produced by rules/decision stages

- `out/audit_log.jsonl`
  - append-only trail of “what happened” events
  - includes `ingest_modules_done` entries that summarize media module outputs

- `out/entity_profiles.json`
  - summaries of observed tracks over time (non-identifying)
  - used by Investigations → Entity Profiles tab

- `out/casebook.json`
  - operator-authored cases/evidence/hypotheses
  - created/updated via Investigations → Casebook tab

- `out/graph.json`
  - a lightweight relationship graph that can include:
    - events + tasks from `events.json`
    - case/evidence/hypothesis from `casebook.json`
    - entity tracks from `entity_profiles.json`

### 2.2 API endpoints (the “window into out/”)

The demo server is a small standard-library HTTP server that serves the static UI and provides JSON endpoints.

Key endpoints used by Sensors + Investigations:

- `GET /api/config`
  - returns YAML config text

- `GET /api/audit?tail=N`
  - returns the last N audit entries

- `GET /api/entity_profiles`
  - returns `out/entity_profiles.json`

- `GET /api/casebook`
  - returns `out/casebook.json` (or a created empty structure)

- `POST /api/casebook`
  - updates the casebook (create case, add evidence, create hypothesis)

- `GET /api/graph`
  - returns `out/graph.json`
  - if missing, attempts to build it best-effort from existing `out/` artifacts

(Other endpoints exist and are used by other pages, but the ones above are the “Sensors + Investigations spine.”)

---

## 3) Sensors page: what it shows and where the data comes from

### 3.1 What the operator sees (UI elements)

The Sensors page is the `#modules` page in the UI.

Main UI elements:

- **Module selector chips** (`#module-nav`)
  - Vision / Audio / Thermal / Gait / Scene

- **Config cards** (`#modules-config`)
  - ingest mode summary
  - module enable/disable summary
  - interpretation hints

- **Module detail card** (`#module-details`)
  - for the currently selected module
  - “Enabled/Disabled” plus last-run fragments

- **Last ingest run** section
  - `#modules-run-meta`: sequence/time of last ingest audit record
  - `#modules-run-stats`: human-readable summary of module outputs
  - `#modules-run-stats-raw`: raw JSON summary for advanced users

### 3.2 What code runs (functions)

At a high level, Sensors is driven by two sources:

1) **Config** (“what is enabled?”)
2) **Audit** (“what actually happened last run?”)

The key UI functions are:

- `loadConfig()`
  - fetches `/api/config`, parses YAML, and calls renderers
  - important for Sensors because it calls `renderModules(cfg)`

- `renderModules(cfg)`
  - reads `cfg.pipeline.ingest` and builds the Sensors page cards
  - populates the module chip bar (`#module-nav`)
  - sets up the ingest setup card (mode/media path/stride/downscale)
  - sets up the enabled analytics list based on `enable_*` toggles
  - calls `renderModuleDetails()` and `renderModulesStats()`

- `renderModuleDetails()`
  - renders the detail panel for the currently selected module
  - uses:
    - `modulesCfgCache` (from config)
    - `moduleStatsCache` (from audit)
  - this is why you can see “Enabled — produced X fragments last run”

- `loadAudit()`
  - fetches `/api/audit` periodically
  - updates `latestAudit` cache
  - triggers `renderModulesStats()` (among other UI updates)

- `renderModulesStats()`
  - looks through `latestAudit` for the most recent `ingest_modules_done`
  - extracts `payload.stats` (counts of fragments per module)
  - updates:
    - `#modules-run-meta`
    - `#modules-run-stats`
    - `#modules-run-stats-raw`
  - also updates `moduleStatsCache` and calls `renderModuleDetails()` so the details page stays in sync

### 3.3 The big idea: Sensors reads *two timelines*

- Config answers: “what should happen?”
- Audit answers: “what did happen?”

That separation matters because:

- You can enable a module in config and still see **0 fragments** if the scene is quiet or your ingest window is short.
- You can also see fragments for a subset of modules even though others are enabled.

---

## 4) Investigations page: what it shows and where the data comes from

The Investigations page is the `#intel` page.

It is a tabbed UI built by JavaScript (it’s not separate HTML pages).

### 4.1 Tab navigation (the “router” inside Investigations)

Investigations has a sub-nav (`#intel-nav`) with tabs:

- Entity Profiles
- Casebook
- Vision Enhancement
- Graph

Core functions:

- `initIntelUI()`
  - runs once the first time you open the Investigations page
  - creates the tab buttons and skeleton layouts
  - attaches click handlers for tab changes

- `showIntelTab(tab)`
  - hides/shows the right `#intel-*` grid

- `loadIntelSelected()`
  - acts like a “tab-specific loader”
  - routes to:
    - `loadEntityProfiles()`
    - `loadCasebook()`
    - `loadGraph()`
    - (Enhancement is user-driven submit)

### 4.2 Entity Profiles tab

Purpose: show non-identifying summaries derived from module outputs.

UI elements:

- `#profiles-refresh` button
- `#profiles-meta` and `#profiles-meta-raw`
- `#profiles-table`
- `#profiles-entity-id` input + `#profiles-show`
- `#profiles-detail` and `#profiles-detail-raw`

Key functions:

- `loadEntityProfiles(force=false)`
  - fetches `/api/entity_profiles`
  - stores in `window.__heliosEntityProfiles`
  - calls `renderEntityProfiles(data)`

- `renderEntityProfiles(data)`
  - fills the table and meta summary
  - clicking a table row calls `renderEntityProfileDetail(data, entity_id)`

- `renderEntityProfileDetail(data, entityId)`
  - shows a compact detail view (recent observations)

How it links back to Sensors:

- The Entity Profiles tab usually only has meaningful data when ingest mode `modules_media` is used.
- That mode is also what the Sensors page is explaining and summarizing.

### 4.3 Casebook tab

Purpose: an operator-editable case/evidence/hypothesis store.

UI elements:

- Create Case form (title/domain/description)
- Add Evidence form (kind/source/URI/case IDs/tags/description)
- Create Hypothesis form (title/confidence/case IDs/evidence IDs/description/rationale)
- Readable views:
  - `#casebook-cases`
  - `#casebook-selected`
  - `#casebook-evidence`
  - `#casebook-hypotheses`
- Raw JSON dump (`#casebook-json`)

Key functions:

- `casebookPost(payload, resultElId)`
  - sends `POST /api/casebook`
  - operations include:
    - `create_case`
    - `add_evidence`
    - `create_hypothesis`

- `loadCasebook(force=false)`
  - fetches `GET /api/casebook`
  - calls `renderCasebookReadable(data)`

- `renderCasebookReadable(data)`
  - renders the selected case and its linked evidence/hypotheses
  - stores the currently selected case ID in `window.__casebookSelectedId`

How it links back to Sensors:

- Casebook is where an operator can “turn sensor observations into a story.”
- The content you add here later becomes part of the Graph tab (because the graph builder reads `out/casebook.json`).

### 4.4 Graph tab (tables + relational canvas + query DSL)

Purpose: connect events, tasks, cases, evidence, and entities.

Think of this as:

- a **table view** (authoritative, deterministic)
- plus a **relational sketch** (the canvas visualization)

UI elements:

- Refresh: `#graph-refresh`
- View mode buttons: `#graph-view-browse`, `#graph-view-query`
- Search: `#graph-search`
- Node type filter chips: `#graph-viz-filters`
- Relational canvas: `#graph-viz`
- Nodes table: `#graph-nodes`
- Edges table: `#graph-edges`

Query DSL elements (inside the Browse card):

- Preset select: `#graph-q-preset`
- Query textarea: `#graph-q`
- Buttons:
  - `#graph-q-run`, `#graph-q-clear`, `#graph-q-use`, `#graph-q-export`
  - `#graph-q-save`, `#graph-q-delete`

Key functions (graph loading/rendering):

- `loadGraph(force=false)`
  - fetches `/api/graph`
  - stores in `window.__heliosGraph`
  - calls `renderGraph(graph)`

- `renderGraph(graph)`
  - builds meta text, raw JSON, and tables
  - applies:
    - search filter (`#graph-search`)
    - node type filter chips (`#graph-viz-filters`)
    - optional query results (when View mode is Query)
  - calls `renderGraphViz(graph)` best-effort

Key functions (relational canvas):

- `renderGraphViz(graph)`
  - builds a small “subgraph” around a focus node (if search is set)
  - animates a force-directed layout
  - supports hover/click-to-focus
  - can highlight nodes/edges when query results are active

Key functions (query DSL):

- `initGraphQueryUI()`
  - wires query UI elements + saved query storage

- `dslTokenize()`, `DSLParser`, `compileExpr()`, `evaluateGraphStatement()`
  - the tokenizer/parser/compiler pipeline
  - output is a `{ nodes: [...], edges: [...] }` result set

How it links back to Sensors:

- The Graph is only as rich as the artifacts you have.
  - If you have only `events.json`, you’ll see mostly events/tasks.
  - If Sensors analytics produced entity profiles, graph can include entities/tracks/cameras.
  - If you created casebook items, you’ll see cases/evidence/hypotheses.

---

## 5) “Interaction” explained: how Sensors feeds Investigations

Here’s the full loop.

### 5.1 Step-by-step flow

1) Config enables analytics
   - Sensors page reads `/api/config`
   - you see e.g. “VISION: on, AUDIO: on, THERMAL: off”

2) You run a pipeline ingest (usually `modules_media`)
   - modules produce fragments
   - the pipeline writes audit entries including `ingest_modules_done`

3) Sensors page shows “what happened”
   - it polls `/api/audit`
   - it extracts `ingest_modules_done.payload.stats`
   - it renders per-module fragment counts

4) Investigations page consumes derived artifacts
   - Entity Profiles tab reads `/api/entity_profiles`
   - Graph tab reads `/api/graph` (which can be built from out artifacts)

5) Casebook adds investigator knowledge
   - Casebook tab writes to `/api/casebook` (updates `out/casebook.json`)
   - Graph tab then includes those casebook nodes/edges

So the relationship is:

- Sensors = “what did the analytics do?”
- Investigations = “how do I understand and organize what happened?”

### 5.2 Why audit is a bridge

Sensors does not parse raw ML outputs. Instead it uses the audit trail as a summary.

That means:

- Sensors stays lightweight and stable (it only needs counts + paths)
- Investigations can focus on meaning and linkage

---

## 6) Function-by-function index (Sensors + Investigations)

This section is a compact “reference map” of the code that implements these pages.

### 6.1 Sensors page function map

- `loadConfig()`
  - **Input:** `/api/config` YAML
  - **Output:** cached parsed config + triggers UI rendering
  - **Calls:** `renderModules(cfg)`

- `renderModules(cfg)`
  - **Input:** parsed config
  - **Output:** module chip nav + cards
  - **Calls:** `renderModuleDetails()`, `renderModulesStats()`

- `updateModuleNavActive()`
  - **Input:** `selectedModule`
  - **Output:** visual selection state

- `renderModuleDetails()`
  - **Input:** `modulesCfgCache`, `moduleStatsCache`, `selectedModule`
  - **Output:** detail card text

- `loadAudit()`
  - **Input:** `/api/audit?tail=N`
  - **Output:** updates `latestAudit`
  - **Calls:** `renderModulesStats()`

- `renderModulesStats()`
  - **Input:** `latestAudit`
  - **Output:** last-run module summary + sets `moduleStatsCache`

### 6.2 Investigations page function map

- `initIntelUI()`
  - **Responsibility:** create tab nav + skeleton cards

- `showIntelTab(tab)`
  - **Responsibility:** hide/show tab grids

- `loadIntelSelected()`
  - **Responsibility:** route loading based on selected tab

Entity Profiles:

- `loadEntityProfiles(force)` → `GET /api/entity_profiles`
- `renderEntityProfiles(data)`
- `renderEntityProfileDetail(data, entityId)`

Casebook:

- `casebookPost(payload, el)` → `POST /api/casebook`
- `loadCasebook(force)` → `GET /api/casebook`
- `renderCasebookReadable(data)`

Graph:

- `loadGraph(force)` → `GET /api/graph`
- `renderGraph(graph)`
- `renderGraphViz(graph)` (+ helpers)
- Query DSL: `initGraphQueryUI()` + tokenizer/parser/compiler/evaluator

---

## 7) Common “why is it empty?” cases

- **Sensors shows enabled modules, but “last run” is empty**
  - No `ingest_modules_done` audit event exists yet.
  - Fix: run ingest in `modules_media` mode.

- **Entity Profiles is empty**
  - `out/entity_profiles.json` hasn’t been produced.
  - Fix: run `modules_media` ingest (and ensure a module that produces profiles is enabled).

- **Graph is empty**
  - No `events.json`, `casebook.json`, or `entity_profiles.json` exist yet.
  - Fix: run pipeline once, or create a casebook item.

- **Things look “fake”**
  - Demo Data is enabled; the UI uses in-browser seeded data instead of calling `/api/*`.

---

## 8) Where this is implemented

UI implementation:

- Sensors + Investigations UI and all their functions live in `ui/index.html`.

Backend API implementation:

- HTTP endpoints are in `src/helios_c2/http_api.py`.

Graph construction:

- Graph builder is in `src/helios_c2/integrations/ontology_graph.py`.

Pipeline overview:

- Architecture context is in `docs/ARCHITECTURE.md`.
