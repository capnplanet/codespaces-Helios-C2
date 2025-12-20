# Helios C2: Multi-Domain Command & Control OS (Reference Implementation)

Helios C2 is a **reference implementation** of a multi-domain command and control platform
that generalizes a simple, facility-scale incident-support pattern into a multi-domain,
multi-echelon operating layer. It is intentionally **non-weaponized** and **simulation-focused**.

This repo does **not** implement classified or production capabilities. It provides:

- An opinionated **data model** for entities, sensors, events, and tasks
- A small set of **services** (ingest, fusion, decision, autonomy, export)
- A **rule engine** and **governance hook** for policy-aware event generation
- A CLI that runs a synthetic, multi-domain scenario to produce Helios events

Think of this as a "hello world" for a Helios-style C2 OS, not as a full Lattice competitor.

## Design Goals

1. **Multi-domain from the start**
   - Domains: air, land, sea, subsea, space, cyber, human, facility
   - Sensors, entities, and events all carry domain tags

2. **Incident-centric core**
   - Alerts are modeled as rich **events** with ID, severity, status and context
   - Events are grouped, prioritized, and passed through a decision pipeline

3. **Human-in-the-loop by default**
   - Autonomy layer only produces **recommendations**, not executable commands
   - All outputs include a short rationale string for operators

4. **Resilient and transparent**
   - All services log audit events
   - A simple governance layer can block or downgrade actions by policy

5. **Grounded in a simple pattern**
   - Ingest → Normalize/Fuse → Apply Rules → Create Events → Recommend Tasks
   - Similar to the repo pattern: detect → alert → triage → log

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run a synthetic theater scenario
python -m helios_c2.cli simulate --scenario examples/scenario_minimal.yaml --out out/
```

This will:

- Load a synthetic scenario with multi-domain sensor inputs
- Run the ingest → fusion → rules → decision → autonomy → export chain
- Write an `events.json` file and an `audit_log.jsonl` file into `out/`

## What This Is / Is Not

- ✅ A teaching and prototyping scaffold for a Helios-style C2 OS
- ✅ Safe to run on a laptop; all "missions" are synthetic
- ❌ A production, safety-critical or weaponized system
- ❌ A representation of any classified capabilities

## Governance & Safety Controls

- Policy hooks can block domains or categories, cap severity by domain, and forbid actions.
- Human-in-the-loop: per-domain approvals with optional auto-approval; pending tasks are audited and withheld from autonomy/export until approved.
- Guardrails: rate-limit tasks per domain/total/per-event to prevent runaway autonomy bursts.
- Exports: JSON file, stdout, and optional webhook; routing works for cloud or on-prem log stacks.
- All governance/guardrail effects are audited (blocked, capped, pending, dropped counts).
- RBAC and signed approvals: optional HMAC tokens per approver to auto-approve tasks; otherwise tasks remain pending.
- Risk budgets: per-tenant critical-task caps with exponential backoff and `risk_hold` status to prevent overload under noisy conditions.
- Evidence: events/tasks carry hashed observables for downstream STIX/TAXII-style export.
- Audit escrow: audit log lines are hash-chained for tamper-evident offline storage.
- STIX 2.1 export: optional bundle generation for interoperability.
- Persistent risk store: optional SQLite-backed critical-task counters across runs.
- Dual-role approvals: domains can require roles; multiple signed approvers can satisfy role requirements.
- 21 CFR Part 11 alignment: audit entries are sequenced, actor-attributed, hash-chained, and optionally HMAC-signed.

## Deployment

Local run (on-prem style) uses the Python CLI shown above. For a containerized, cloud-agnostic run:

```bash
docker build -t helios-c2 .
docker run --rm -v "$PWD/out:/app/out" helios-c2 \
   python -m helios_c2.cli simulate --scenario examples/scenario_minimal.yaml --out out
```

The container image has no cloud-provider dependencies; you can deploy it to Kubernetes, ECS, Nomad, or bare-metal with the same artifact.

Policy packs: supply a governance/guardrail preset (e.g., configs/policy_safety.yaml):

```bash
python -m helios_c2.cli simulate \
   --scenario examples/scenario_minimal.yaml \
   --out out/ \
   --policy-pack configs/policy_safety.yaml
   # Optional signed approvals
   --approver-id auto --approver-token "$(python - <<'PY'
import hmac, hashlib, base64
secret = "changeme"
msg = "ev:any:investigate:default"
mac = hmac.new(secret.encode(), msg=msg.encode(), digestmod=hashlib.sha256).digest()
print(base64.urlsafe_b64encode(mac).decode().rstrip('='))
PY)"
   # STIX export
   --config configs/default.yaml
```

Generated: 2025-12-20
