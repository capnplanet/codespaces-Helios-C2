# Advancing the State of the Art (What This Repo Adds)

This repo assumes mature multi-domain C2 and security platforms exist.
The goal here is not to compete with full-featured platforms, but to make a few hard-to-evaluate properties **explicit, testable, and reusable**.

This document describes the advances this repo aims to demonstrate, grounded in concrete code.

## Framing (what we do and do not claim)

- This is a **teaching/simulation** repo.
- All “actions” are **simulated outputs** (files, optional HTTP posts for demo/mocking).
- Many mature systems already implement complex workflows, ROE-like constraints, and authorization chains.

Helios focuses on being a compact reference for:

- end-to-end governance and oversight across analytics → recommendations → (simulated) actuation
- auditability and provenance you can verify offline
- investigation-oriented representations that connect machine outputs to human reasoning artifacts

## Advances (offset areas) implemented here

### 1) A unified governance + guardrails + approvals envelope

Helios applies a consistent policy and oversight envelope across:

- events
- recommended tasks
- derived “infrastructure tasks” (simulated)
- simulated platform commands

Where it lives:

- Governance policy: [src/helios_c2/governance.py](../src/helios_c2/governance.py)
- Guardrails + risk budgets: [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py), [src/helios_c2/risk_store.py](../src/helios_c2/risk_store.py)
- Approvals/RBAC: [src/helios_c2/services/decider.py](../src/helios_c2/services/decider.py)
- Policy pack example: [configs/policy_safety.yaml](../configs/policy_safety.yaml)

Why it matters:

- It allows “what the system suggests” and “what the system would do” to be constrained by the same policy surface.
- It provides a concrete place to study overload control (rate limits, per-asset caps, risk budgets) without needing a full platform.

### 2) Tamper-evident (and optionally signed) audit across the full run

Helios produces an append-only audit trail with hash chaining and optional HMAC signing.
It is designed to support offline verification.

Where it lives:

- Audit implementation: [src/helios_c2/audit.py](../src/helios_c2/audit.py)
- Used end-to-end in the pipeline: [src/helios_c2/orchestrator.py](../src/helios_c2/orchestrator.py)

Why it matters:

- Oversight is not only “policy at runtime,” but also “provable provenance after the fact.”
- The same audit channel can record both automation steps and human approvals (via the API).

### 3) A compact investigations layer (casebook + relationship graph)

This repo includes best-effort investigation helpers that connect:

- sensor-derived events
- task recommendations and simulated commands
- assets
- operator-authored case notes (cases, evidence, hypotheses)

Where it lives:

- Casebook schema + persistence: [src/helios_c2/integrations/casebook.py](../src/helios_c2/integrations/casebook.py)
- Relationship graph builder: [src/helios_c2/integrations/ontology_graph.py](../src/helios_c2/integrations/ontology_graph.py)
- UI exploration (including a small query DSL): [ui/index.html](../ui/index.html)

Why it matters:

- It creates a “bridge object” between machine outputs and human reasoning artifacts.
- It enables repeatable evaluation questions like “can an operator trace recommendations back to evidence and policy?”

### 4) Privacy-conscious entity summaries (non-identifying)

When using media-module ingest, Helios can generate coarse, non-identifying entity summaries.
These are for pattern-oriented analysis and teaching, not identity resolution.

Where it lives:

- Entity profiler integration: [src/helios_c2/integrations/entity_profiler.py](../src/helios_c2/integrations/entity_profiler.py)
- Explanation doc: [ENTITY_PROFILER_FEYNMAN.md](ENTITY_PROFILER_FEYNMAN.md)

Why it matters:

- Provides a concrete place to study multi-modal analytics + privacy constraints.

### 5) Explainability-ready narrative reporting (LLM hooks with provenance)

This repo includes structured narrative reporting with provider hooks for LLM summarization/explanation.
The default mode can run without an external model.

Where it lives:

- Narrative/explainability module: [src/helios_c2/modules/summarize_llm.py](../src/helios_c2/modules/summarize_llm.py)

Why it matters:

- Makes “assistant-generated narrative” an explicit artifact that can be evaluated (quality, failure modes, provenance), rather than an opaque UI feature.

## What closure work looks like (without expanding scope)

- Strengthen the positioning and comparison story: [STATE_OF_THE_ART.md](STATE_OF_THE_ART.md)
- Define a concrete roadmap and evaluation harness: [PROGRAM_PLAN.md](PROGRAM_PLAN.md), [EVALUATION_AND_METRICS.md](EVALUATION_AND_METRICS.md)
- Keep the code changes minimal and focused on enabling repeatable experiments, not building a full platform
