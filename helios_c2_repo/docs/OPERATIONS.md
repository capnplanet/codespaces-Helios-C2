# Operations

This reference repo runs a synthetic scenario through the Helios services.

- `examples/scenario_minimal.yaml` defines a handful of multi-domain readings
- `configs/default.yaml` configures domains, rule thresholds, and export options
- The CLI (`helios_c2.cli`) coordinates the run

Outputs:

- `events.json`: list of Events and TaskRecommendations
- `audit_log.jsonl`: append-only log of service steps

Governance controls:

- Configure `pipeline.governance.block_domains` or `block_categories` to drop events before decisioning.
- Use `pipeline.governance.severity_caps` (domain -> max severity) to cap event severity without suppressing them.
- Forbidden actions (`pipeline.governance.forbid_actions`) raise and are logged during decisioning.

Human-in-the-loop:

- `pipeline.human_loop.domain_require_approval` or `default_require_approval` forces approvals per domain.
- `auto_approve` controls whether tasks are auto-approved (kept) or marked `pending_approval` and withheld.
- `approver` sets the actor string recorded on auto-approvals.
- `pipeline.rbac.approvers` defines approver secrets; `pipeline.rbac.active_approver` (or CLI flags) provide ID/token for signed auto-approval.
- If no valid token is provided, tasks stay `pending_approval`.
- `pipeline.rbac.required_roles` can demand specific roles (per domain); auto-approval requires signed tokens from approvers covering those roles.

Guardrails:

- `pipeline.guardrails.rate_limits.per_domain` caps tasks per domain per run.
- `pipeline.guardrails.rate_limits.total` caps total tasks per run.
- `pipeline.guardrails.rate_limits.per_event` caps tasks spawned per event.
- `pipeline.guardrails.risk_budgets` caps critical tasks per tenant; overages move tasks to `risk_hold` with exponential backoff (`risk_backoff_base_sec`).
- `pipeline.guardrails.health_alert_drop_ratio` triggers an audit alert when guardrails drop more than the ratio of tasks.
- `pipeline.guardrails.risk_store_path` enables SQLite-backed counters across runs; `risk_window_sec` controls reset window.

Export targets:

- `pipeline.export.formats` accepts `json` (default) and `stdout` to send results to log collectors in cloud or on-prem deployments.
- `pipeline.export.webhook` can POST the full export payload to an HTTP endpoint (optional, best-effort with audit on failure).
- `pipeline.export.formats` can include `stix` to emit a STIX 2.1 bundle (`events_stix.json`).

Audit escrow:

- Audit log entries are hash-chained (`prev_hash`, `hash`) for tamper-evident offline storage.
- Optional HMAC signing (`audit.sign_secret`) adds electronic signatures per entry; `audit.actor` records the originator.
