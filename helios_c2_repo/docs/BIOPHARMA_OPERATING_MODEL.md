# Biopharma Operating Model (GxP Manufacturing + QA MVP)

This document defines a non-military, non-law-enforcement operating model for evolving this repo into a unified biopharma operations network.

## MVP slice

Initial MVP scope is **GxP Manufacturing + QA**.

In-scope workflows (simulation-first):

- process deviation detection and triage
- lot/batch hold recommendations
- OOS and major deviation escalation
- CAPA initiation recommendations
- approval-gated release workflow signals

Out of scope for MVP:

- direct control of physical equipment
- replacing validated system-of-record tools (MES/LIMS/QMS/ERP)
- autonomous execution without configured human approval gates

## System role

The platform acts as a cross-system oversight and orchestration layer that:

- ingests operational quality/manufacturing signals
- normalizes them into a common event/task model
- applies governance and role-based approvals
- writes auditable outputs for downstream systems

## Closed-loop boundary

Closed-loop in this MVP means **approval-gated digital workflow actions** (for example, create quality records, update hold/release statuses in integrated systems), not direct plant actuation.

## Core GxP control principles

- human review for high-impact quality/manufacturing actions
- segregation of duties through RBAC role requirements
- tamper-evident audit trail for all decision transitions
- risk and rate guardrails to prevent runaway automation

## Starter artifacts

- Config: [configs/gxp_mfg_qa.yaml](../configs/gxp_mfg_qa.yaml)
- Rules: [configs/rules_gxp_mfg_qa.yaml](../configs/rules_gxp_mfg_qa.yaml)
- Scenario: [examples/scenario_gxp_mfg_qa.yaml](../examples/scenario_gxp_mfg_qa.yaml)

## Suggested run

```bash
PYTHONPATH=src python -m helios_c2.cli simulate \
  --scenario examples/scenario_gxp_mfg_qa.yaml \
  --config configs/gxp_mfg_qa.yaml \
  --out out_gxp
```

Then inspect:

- `out_gxp/events.json`
- `out_gxp/audit_log.jsonl`
- `out_gxp/infrastructure_actions.jsonl` (when enabled)
- `out_gxp/metrics.prom`
