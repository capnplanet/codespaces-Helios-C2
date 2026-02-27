# Compliance Baseline (US + EU, GxP MFG/QA MVP)

This is a practical baseline for implementation planning in this repo. It is not legal advice.

## Intended baseline

- US: 21 CFR Part 11-aligned electronic records/signatures controls
- EU: Annex 11-oriented computerized system controls
- Privacy baseline: GDPR-aware handling for personal data where present

## MVP compliance control objectives

### 1) Electronic records integrity

- immutable/tamper-evident audit records for decision transitions
- clear event/task provenance links to source artifacts
- controlled retention and retrieval strategy for regulated records

### 2) Electronic signature context

- signature must bind to action, actor identity, timestamp, and meaning
- support dual-approval patterns where policy requires it
- role requirements must be enforceable and testable

### 3) Access and segregation of duties

- role-based approval requirements for quality-critical actions
- separation between recommendation generation and final authorization
- explicit denial/override trails in audit logs

### 4) Change and validation discipline

- requirements-to-test traceability for governed workflows
- documented release criteria and evidence package per milestone
- repeatable test suites for governance, approvals, and audit behavior

## MVP artifact mapping

- Governance + approvals config: [configs/gxp_mfg_qa.yaml](../configs/gxp_mfg_qa.yaml)
- Rule logic: [configs/rules_gxp_mfg_qa.yaml](../configs/rules_gxp_mfg_qa.yaml)
- Scenario harness: [examples/scenario_gxp_mfg_qa.yaml](../examples/scenario_gxp_mfg_qa.yaml)
- Audit implementation: [src/helios_c2/audit.py](../src/helios_c2/audit.py)
- Decision/approval logic: [src/helios_c2/services/decider.py](../src/helios_c2/services/decider.py)

## Near-term gaps to close

- stronger identity binding than static shared secrets in config
- formal record retention/archival policy controls
- explicit e-signature manifestation fields in all approval artifacts
- documented validation package structure for inspection readiness
