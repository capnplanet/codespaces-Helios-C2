# State of the Art (Context + Positioning)

This repo is a **teaching and simulation** reference implementation of a multi-domain incident-support / C2-style pipeline.
It is intentionally small and self-contained so governance, approvals, guardrails, and auditability are visible end-to-end.

This document exists for two reasons:

1. Acknowledge that **multi-domain** and **coalition / multi-organization** command-and-control and security operations platforms already exist and are mature.
2. Position what Helios is (and is not) trying to demonstrate: an **overlay-style governance + audit + investigations envelope** that can be studied independently of any single vendor/platform.

## Scope and non-goals

Helios does **not** attempt to replace:

- mature common operating pictures (COPs), tracks, and mission planning tools
- platform-specific tactical applications
- enterprise data backbones and message buses
- real actuator integrations (all “actions” here are simulated outputs)

Helios does attempt to make **governance, approvals, guardrails, and audit** first-class and testable across the full pipeline.

## Examples of mature platforms (illustrative)

Public descriptions of the modern ecosystem include systems and initiatives such as:

- Joint / coalition interoperability efforts (e.g., CJADC2/JADC2-related programs)
- Tactical and mission applications (e.g., ATAK-like ecosystems)
- Cloud-enabled battle management and cross-domain data services (e.g., ABMS-like programs)
- Operations-center tooling (e.g., TOC-style suites)
- Coalition data sharing / collaboration systems (e.g., products such as Solipsys BC3 or Kiinnami AmiShare)
- Master data management / integration platforms used to unify “things” across domains (e.g., MDM-style platforms; integration vendors; C5ISR integration providers)
- Domestic and private-sector security operations platforms (e.g., modern VMS fused with access control, IoT sensors, and incident workflows)

This list is not exhaustive and is not an endorsement. It is a reminder that many “multi-domain integration” concerns are already addressed in mature products.

## What mature systems typically already do well

Common capabilities in mature C2 / security systems often include:

- multi-domain ingest and visualization (geo, time, track history)
- robust identity, access control, and operator roles
- rule frameworks and alerting (often much richer than simple demo rules)
- authorization chains, ROE-like constraints, and workflow approvals
- exclusion zones / geofences / “do-not-act” constraints and cross-domain policies
- integrations with many sensors and enterprise systems
- hardened deployment, redundancy, and operational support

## Where Helios fits

Helios is best understood as a **governance + audit + investigations overlay** and an evaluation harness.

Concrete focus areas implemented in this repo:

- **Policy governance** (block domains/categories, cap severity, forbid actions): [src/helios_c2/governance.py](../src/helios_c2/governance.py)
- **Approvals + RBAC** (including signed approvals via HMAC): [src/helios_c2/services/decider.py](../src/helios_c2/services/decider.py)
- **Guardrails + risk budgets** (rate limiting + persistent counters): [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py), [src/helios_c2/risk_store.py](../src/helios_c2/risk_store.py)
- **Tamper-evident audit trail** (hash-chained, optionally signed): [src/helios_c2/audit.py](../src/helios_c2/audit.py)
- **Investigation helpers** (casebook + relationship graph + entity summaries):
  - [src/helios_c2/integrations/casebook.py](../src/helios_c2/integrations/casebook.py)
  - [src/helios_c2/integrations/ontology_graph.py](../src/helios_c2/integrations/ontology_graph.py)
  - [src/helios_c2/integrations/entity_profiler.py](../src/helios_c2/integrations/entity_profiler.py)

## Comparison matrix (explicit + measurable)

This table is intentionally conservative. It avoids claiming uniqueness for things that are common in mature platforms.
The emphasis is on what Helios makes **explicit and testable** in a compact reference implementation.

| Capability area | Common in mature platforms | Helios scope (this repo) | How to measure here (artifacts/tests) | Extension / non-goal |
|---|---|---|---|---|
| Multi-domain ingest | Yes | Scenario YAML + tail JSONL + optional media modules ingest: [src/helios_c2/services/ingest.py](../src/helios_c2/services/ingest.py) | Run scenarios under [examples](../examples). Inspect `out/events.json` and `out/audit_log.jsonl`. Baseline coverage: [tests/test_demo_pipeline.py](../tests/test_demo_pipeline.py) | External feed adapters are future work |
| Rules → events | Yes | Simple rules engine producing `Event` with evidence: [src/helios_c2/rules_engine.py](../src/helios_c2/rules_engine.py) | Inspect `events.json` event list and evidence fields. Rules examples: [configs/rules.sample.yaml](../configs/rules.sample.yaml) | Not aiming to replicate enterprise rule platforms |
| Authorization / approvals | Yes | Config-driven approvals + optional signed approvals (HMAC) and role requirements: [src/helios_c2/services/decider.py](../src/helios_c2/services/decider.py) | Verify `TaskRecommendation.status` and approval metadata in `events.json`. Tests: [tests/test_stix_and_rbac.py](../tests/test_stix_and_rbac.py) | Mapping to real identity providers is future work |
| Governance policy | Mixed (varies by system) | Drop domains/categories, cap severity, forbid actions: [src/helios_c2/governance.py](../src/helios_c2/governance.py) | Configure blocks/caps in `configs/*.yaml` and observe filtered outputs. Tests: [tests/test_governance.py](../tests/test_governance.py) | Policy authoring UX/tooling is future work |
| Guardrails + overload control | Mixed | Per-domain/per-event/total caps, per-asset caps, persistent risk budgets: [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py), [src/helios_c2/risk_store.py](../src/helios_c2/risk_store.py) | Inspect guardrail/risk entries in `audit_log.jsonl` and resulting task statuses. Tests: [tests/test_guardrails.py](../tests/test_guardrails.py), [tests/test_audit_and_risk.py](../tests/test_audit_and_risk.py) | Long-running streaming control loops are future work |
| Auditability / provenance | Often present, varies | Hash-chained audit log with optional signing + verification: [src/helios_c2/audit.py](../src/helios_c2/audit.py) | Verify audit chain on startup and inspect `audit_log.jsonl`. Tests: [tests/test_audit_and_risk.py](../tests/test_audit_and_risk.py) | External SIEM/log-store integration is future work |
| Investigations layer | Often present, varies | Casebook + relationship graph + UI query DSL: [src/helios_c2/integrations/casebook.py](../src/helios_c2/integrations/casebook.py), [src/helios_c2/integrations/ontology_graph.py](../src/helios_c2/integrations/ontology_graph.py), [ui/index.html](../ui/index.html) | Generate/inspect `out/graph.json` and `out/casebook.json` (best-effort). Use UI Investigations pages via [src/helios_c2/http_api.py](../src/helios_c2/http_api.py) | Not a full enterprise knowledge graph |
| Actuation / effectors | Yes (operationally) | Simulated-only infrastructure actions and platform commands: [src/helios_c2/adapters/infrastructure.py](../src/helios_c2/adapters/infrastructure.py), [src/helios_c2/adapters/platform_link.py](../src/helios_c2/adapters/platform_link.py) | Inspect `out/infrastructure_actions.jsonl` and `out/platform_commands.json` when enabled. Tests: [tests/test_infrastructure.py](../tests/test_infrastructure.py) | Real integrations are explicitly out of scope |

## If you want the “what we advance” story

See [ADVANCING_SOA.md](ADVANCING_SOA.md) for the specific areas this repo focuses on advancing, grounded to the code and tests.
