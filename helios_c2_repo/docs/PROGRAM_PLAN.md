# Program Plan (TRL-Aligned)

This repo already contains an executable, tested prototype. The remaining closure work is primarily:

- positioning vs mature systems (what we add and what we do not claim)
- an explicit TRL-style roadmap
- a concrete evaluation plan with measurable outcomes

This document outlines a phased plan that stays grounded in what exists today.

## MVP scope pivot (current)

The current MVP slice is **GxP Manufacturing + QA** (not Clinical Operations).

- Operating model and boundary: [BIOPHARMA_OPERATING_MODEL.md](BIOPHARMA_OPERATING_MODEL.md)
- Compliance baseline (US+EU): [COMPLIANCE_BASELINE.md](COMPLIANCE_BASELINE.md)
- Starter runnable assets:
  - config: [configs/gxp_mfg_qa.yaml](../configs/gxp_mfg_qa.yaml)
  - rules: [configs/rules_gxp_mfg_qa.yaml](../configs/rules_gxp_mfg_qa.yaml)
  - scenario: [examples/scenario_gxp_mfg_qa.yaml](../examples/scenario_gxp_mfg_qa.yaml)

## Guiding principles

- Keep scope aligned with this repo: simulation, teaching, and evaluation harness.
- Prefer “overlay” integrations (governance/audit/investigations) over replacing full platforms.
- Every milestone must have a runnable demo and measurable artifacts (audit, metrics, exports, UI states).

## Phase 0–1: Baseline prototype package (TRL 2 → 3)

Goal: make the existing prototype easy to run, inspect, and evaluate as a baseline.

Work items:

- Tighten documentation cross-links and positioning:
  - [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md)
  - [ADVANCING_SOA.md](ADVANCING_SOA.md)
- Define baseline experiment scenarios and expected outputs:
  - [examples/scenario_minimal.yaml](../examples/scenario_minimal.yaml)
  - [examples/scenario_infra.yaml](../examples/scenario_infra.yaml)
- Ensure governance/approvals/guardrails/audit behaviors are easy to toggle via configs:
  - [configs/default.yaml](../configs/default.yaml)
  - [configs/policy_safety.yaml](../configs/policy_safety.yaml)
  - [configs/gxp_mfg_qa.yaml](../configs/gxp_mfg_qa.yaml)

Deliverables (repo artifacts):

- A clear positioning + comparison story: [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md), [ADVANCING_SOA.md](ADVANCING_SOA.md)
- A runnable evaluation harness and metrics: [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)
- A traceable feedback-response map: [REVIEW_RESPONSE.md](REVIEW_RESPONSE.md)
- A simulation-only multi-arm runner for policy/config comparisons with summary output (`simulate_arms` + `comparison_summary.json`)

Exit criteria (checklist):

- [ ] A new user can follow [USER_GUIDE.md](USER_GUIDE.md) to run a baseline scenario end-to-end.
- [ ] Baseline run using [examples/scenario_minimal.yaml](../examples/scenario_minimal.yaml) + [configs/default.yaml](../configs/default.yaml) produces:
  - [ ] `out/events.json`
  - [ ] `out/audit_log.jsonl`
  - [ ] `out/metrics.prom` (when `metrics` export is enabled)
- [ ] Strict-policy run using [examples/scenario_infra.yaml](../examples/scenario_infra.yaml) + [configs/policy_safety.yaml](../configs/policy_safety.yaml) produces:
  - [ ] infrastructure actions (when enabled) and corresponding audit entries
  - [ ] pending approvals and/or holds when configured
- [ ] GxP MVP run using [examples/scenario_gxp_mfg_qa.yaml](../examples/scenario_gxp_mfg_qa.yaml) + [configs/gxp_mfg_qa.yaml](../configs/gxp_mfg_qa.yaml) produces:
  - [ ] quality/manufacturing events and approval-gated tasks
  - [ ] hold/deviation/CAPA workflow recommendations in artifacts
  - [ ] audit evidence for approvals and guardrails
- [ ] Core control surfaces are covered by tests:
  - [ ] governance: [tests/test_governance.py](../tests/test_governance.py)
  - [ ] guardrails/risk budgets: [tests/test_guardrails.py](../tests/test_guardrails.py), [tests/test_audit_and_risk.py](../tests/test_audit_and_risk.py)
  - [ ] approvals/RBAC: [tests/test_stix_and_rbac.py](../tests/test_stix_and_rbac.py)
  - [ ] infrastructure export behavior: [tests/test_infrastructure.py](../tests/test_infrastructure.py)
- [ ] Multi-arm harness run (same scenario, at least two arms) produces per-arm outputs plus `comparison_summary.json`.

## Phase 2: Strengthen analytics + investigations as an overlay (TRL 3 → 4)

Goal: improve the fidelity and utility of the analytics and investigations layer without expanding into a full platform.

Work items:

- Integrate selected prototype capabilities more explicitly (as optional modules):
  - entity summaries and pattern-of-life-like aggregates (non-identifying)
  - conservative media enhancement and redaction workflows
- Standardize investigation artifacts for repeatability:
  - relationship graph (`graph.json`) stability
  - casebook schema evolution and backward compatibility

Deliverables (repo artifacts):

- Optional modules/integrations that improve investigations and analytics without changing the core oversight envelope
- A stable set of investigation artifacts and queries (graph + casebook) suitable for repeatable evaluation

Exit criteria (checklist):

- [ ] Demonstrate repeatable improvements on defined metrics (see [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)) across at least two scenario/config “arms.”
- [ ] Investigation artifacts are present and usable for the defined scenarios:
  - [ ] `out/graph.json` (or on-demand graph generation via the API)
  - [ ] `out/casebook.json` with at least one case/evidence/hypothesis created via the UI
- [ ] Oversight remains uniform: governance/approvals/guardrails/audit still constrain any derived tasks and simulated actions.

## Phase 3: External integration as an overlay (TRL 4 → 5)

Goal: validate that the governance/audit/investigations envelope can sit alongside an existing platform.

Approach:

- Add adapters that translate external platform outputs into `SensorReading` / `Event` / `TaskRecommendation` shapes.
- Keep actuation out of scope; focus on provenance, policy evaluation, and investigation artifacts.

Deliverables (repo artifacts):

- One or more adapters that map an external feed format (or realistic mock) into the repo’s normalized data shapes
- Repeatable runs that produce the same core artifacts (`events.json`, `audit_log.jsonl`) under the same inputs

Exit criteria (checklist):

- [ ] Demonstrate ingest of a representative external feed (or a realistic mock) with stable outputs and auditability.
- [ ] Demonstrate that policy + approvals can be applied consistently to externally derived recommendations.
- [ ] Maintain the overlay boundary: no real actuation; effectors remain simulated.

## Key risks and mitigations

- Risk: Over-claiming novelty vs mature platforms
  - Mitigation: keep claims tied to specific artifacts and code; use [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md) and conservative language.

- Risk: Evaluation becomes subjective
  - Mitigation: define objective metrics from audit/metrics exports and structure operator studies with clear tasks (see [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)).

- Risk: Integration scope creep
  - Mitigation: enforce “overlay-only” integration boundaries; simulated actuation remains simulated.

## Deliverables (repo artifacts)

- Positioning docs: [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md), [ADVANCING_SOA.md](ADVANCING_SOA.md)
- Evaluation plan: [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)
- Traceability to review feedback: [REVIEW_RESPONSE.md](REVIEW_RESPONSE.md)
