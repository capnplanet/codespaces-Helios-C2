# Evaluation and Metrics

This repo is designed so that important properties are measurable using artifacts it already produces:

- `audit_log.jsonl` (tamper-evident audit)
- `events.json` (events + approved tasks + pending tasks)
- `metrics.prom` (counters/timers when enabled)
- best-effort artifacts (`graph.json`, `casebook.json`, `entity_profiles.json`)

The goal of this document is to define repeatable evaluation questions and metrics grounded in those artifacts.

## Evaluation harness (what exists today)

### Scenarios

- Minimal multi-domain baseline: [examples/scenario_minimal.yaml](../examples/scenario_minimal.yaml)
- Infrastructure mapping scenario: [examples/scenario_infra.yaml](../examples/scenario_infra.yaml)

### Config “arms”

- Baseline config: [configs/default.yaml](../configs/default.yaml)
- Stricter governance/approvals/guardrails policy pack: [configs/policy_safety.yaml](../configs/policy_safety.yaml)

### UI + API

- API/UI server: [src/helios_c2/http_api.py](../src/helios_c2/http_api.py)
- UI (single file): [ui/index.html](../ui/index.html)

## Experiment families

### 1) Oversight enforcement (governance, approvals, guardrails)

Questions:

- Do governance policies consistently filter/limit outputs across domains?
- Do approval requirements produce pending tasks as expected?
- Under overload, do guardrails and risk budgets hold back tasks and produce audit alerts?

Metrics (examples):

- **Governance drop rate**: fraction of events dropped due to policy blocks.
- **Approval pending rate**: fraction of tasks in `pending_approval`.
- **Guardrail drop ratio**: fraction of tasks dropped by rate limits.
- **Risk-hold rate**: fraction of tasks in `risk_hold`.

Artifacts:

- `events.json` for final task statuses.
- `audit_log.jsonl` for explicit `guardrails` and `risk_budget` audit entries.

Related tests:

- [tests/test_governance.py](../tests/test_governance.py)
- [tests/test_guardrails.py](../tests/test_guardrails.py)
- [tests/test_audit_and_risk.py](../tests/test_audit_and_risk.py)

### 2) Provenance and accountability

Questions:

- Can a reviewer reconstruct “what happened and why” from audit + exported artifacts?
- Can tampering be detected via hash-chain verification?

Metrics (examples):

- **Audit completeness**: required milestone events present (run_start, rules_done, decision_done, run_end).
- **Audit verification success**: chain verification passes for unmodified logs and fails on modified logs.

Artifacts:

- `audit_log.jsonl` plus audit verification behavior.

Related tests:

- [tests/test_audit_and_risk.py](../tests/test_audit_and_risk.py)

### 3) Investigations utility (graph + casebook)

Questions:

- Can an operator link recommendations back to evidence, and group related items into a case?
- Does the relationship graph include the expected node and edge types for a scenario?

Metrics (examples):

- **Graph coverage**: expected node types present (event, task, asset, case, evidence).
- **Trace depth**: shortest path length between `task:*` nodes and their supporting evidence nodes.
- **Case completeness**: number of evidence items attached per case for a scenario.

Artifacts:

- `graph.json` (or `GET /api/graph`), `casebook.json`.

### 4) Human-in-the-loop workflows (operator study)

This repo’s UI can support lightweight, repeatable operator tasks.

Study variables (examples):

- With vs without the Investigations tools (graph + casebook)
- With vs without narrative/explainability artifacts (when enabled)
- Baseline vs strict governance/approval policy

Outcomes (examples):

- Time-to-triage: time to correctly identify the highest-severity event(s)
- Error rate: incorrect approvals/denials under policy constraints
- Traceability: ability to cite supporting evidence for a decision

Instrumentation:

- Use `audit_log.jsonl` as the primary log of user actions and system outputs.
- Capture UI actions via the API endpoints that already log decisions.

## Practical run recipe

Baseline run:

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_minimal.yaml \
  --config configs/default.yaml \
  --out out
```

Strict policy run (example):

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_infra.yaml \
  --config configs/policy_safety.yaml \
  --out out
```

Then serve UI/API:

```bash
PYTHONPATH=src python -m helios_c2.http_api \
  --out out \
  --config configs/default.yaml \
  --ui-dir ui \
  --host 0.0.0.0 \
  --port 8080
```

## Notes on interpretation

- This repo is intentionally not a full operational system.
- When comparing results across configurations, treat the goal as “oversight properties and evidence quality,” not platform feature parity.
