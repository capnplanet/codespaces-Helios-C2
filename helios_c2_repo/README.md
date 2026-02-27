# Helios C2

Helios C2 is a **simulation-focused teaching repo** for a multi-domain incident-support / C2-style pipeline.
It ingests synthetic sensor readings, turns them into events, generates task recommendations, and applies governance,
approvals, guardrails, and a tamper-evident audit trail end-to-end.

This is **not** a weapon system, **not** a production C2 platform, and the included “actions” are **simulated only**.

## What’s In Here

- Pipeline stages: ingest → fusion → rules → decision → guardrails/risk budgets → autonomy plan → export
- Oversight/safety primitives:
   - policy governance (block domains/categories, cap severity, forbid actions)
   - human-in-the-loop approvals with optional signed approvals (RBAC via HMAC)
   - rate limits + risk budgets (SQLite-backed counters supported)
   - hash-chained audit log with optional signing
- Exports: `events.json`, `metrics.prom`, optional STIX 2.1, optional webhook POST, optional JSONL streams
- Demo UI + HTTP API for exploring `out/` artifacts
- Optional “investigations” helpers: casebook, ontology graph, entity profiles (best-effort)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Run a scenario (writes outputs into out/)
python -m helios_c2.cli simulate \
   --scenario examples/scenario_minimal.yaml \
   --config configs/default.yaml \
   --out out

# Serve the demo UI + API (reads from out/)
python -m helios_c2.http_api \
   --out out \
   --config configs/default.yaml \
   --ui-dir ui \
   --host 0.0.0.0 \
   --port 8080
```

Open `http://localhost:8080`.

## Outputs (What You’ll See On Disk)

Common artifacts under `out/`:

- `events.json`: events, approved tasks, and pending tasks
- `audit_log.jsonl`: hash-chained (and optionally signed) audit trail
- `metrics.prom`: Prometheus text exposition (when enabled)
- Optional: `events_stix.json`, `tasks.jsonl`, `infrastructure_actions.jsonl`
- Optional: `graph.json`, `casebook.json`, `entity_profiles.json`, `assets.json`, `platform_commands.json`

## Documentation

Start with:

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — how to run the demo + UI
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — config knobs (governance, approvals, guardrails, exports)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — pipeline wiring and responsibilities

Positioning and evaluation:

- [docs/STATE_OF_THE_ART.md](docs/STATE_OF_THE_ART.md) — context + positioning vs mature platforms
- [docs/ADVANCING_SOA.md](docs/ADVANCING_SOA.md) — what this repo adds (grounded to code)
- [docs/PROGRAM_PLAN.md](docs/PROGRAM_PLAN.md) — phased roadmap (TRL-aligned)
- [docs/EVALUATION_AND_METRICS.md](docs/EVALUATION_AND_METRICS.md) — evaluation harness and measurable metrics
- [docs/REVIEW_RESPONSE.md](docs/REVIEW_RESPONSE.md) — traceability to common review concerns
- [docs/PLATFORM_FEYNMAN.md](docs/PLATFORM_FEYNMAN.md) — the whole platform explained simply
- [docs/ENTITY_PROFILER_FEYNMAN.md](docs/ENTITY_PROFILER_FEYNMAN.md) — entity profiler explained simply
- [docs/INVESTIGATIVE_SUPPORT_FEYNMAN.md](docs/INVESTIGATIVE_SUPPORT_FEYNMAN.md) — investigative support explained simply
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — core data types and artifacts

## Safety / Accuracy Notes

- Approval behavior is configurable. The default config is intentionally “demo-friendly”; if you want strict signed approvals, configure `pipeline.rbac.*` and disable unsigned auto-approval.
- HTTP egress is optional: webhook and infrastructure forwarding only occur when explicitly configured.
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
