Helios C2 Demo UI
=================

This lightweight demo UI lets you navigate the key pipeline concerns:

- Dashboard: high-level counters and timings (real metrics file driven)
- Approvals: shows approval defaults per action and their enforcement status (real)
- Guardrails: shows per-asset and pattern-based rate limits (real)
- Modules: surfaces media-module ingest configuration and last ingest stats (real)
- Audit Trail: dedicated page to browse/export the signed hash-chain (real)
- Infra Effector: shows file/HTTP export status with mock send (mocked HTTP)

Each page indicates whether data is live or mock and describes intended behavior.

Run locally (UI + API wrapper)
------------------------------

Start the lightweight API/UI server (serves UI and reads exports):

```
python -m helios_c2.http_api --out out --config configs/default.yaml --ui-dir ui --host 0.0.0.0 --port 8080
```

Then open http://localhost:8080 in your browser.

Data sources (via /api/*)
-------------------------

- /api/metrics -> metrics.prom (when `pipeline.export.formats` includes `metrics`).
- /api/events -> events.json (events/tasks/pending_tasks after a run).
- /api/intents -> intents.json (ingested commander intent, if present).
- /api/playbook_actions -> playbook_actions.json (mapped actions from intent).
- /api/platform_commands -> platform_commands.json (commands and delivery status).
- /api/audit -> tail of audit_log.jsonl.
- /api/config -> the active pipeline config (YAML).

Modules page uses /api/config for toggles/mode and /api/audit to surface the last `ingest_modules_done` stats.

Notes
-----
- Infra page still uses a mock HTTP trigger; no outbound calls are made.
- When running `modules_media` ingest, the resulting events/tasks will show up on the Data page once the pipeline finishes.
