# Operations

This repo runs a synthetic scenario through the Helios services (batch-style). Ingest can read:

- a YAML scenario (`pipeline.ingest.mode: scenario`)
- a JSONL file (`pipeline.ingest.mode: tail`)
- a local media file via built-in modules (`pipeline.ingest.mode: modules_media`)

- `examples/scenario_minimal.yaml` defines a handful of multi-domain readings for batch runs
- `examples/scenario_minimal.jsonl` is a JSONL variant for tail-based ingest
- `configs/default.yaml` configures domains, rule thresholds, ingest mode, and export options
- The CLI (`helios_c2.cli`) coordinates the run

CLI entrypoint

- The CLI currently exposes `simulate` (there is no separate long-running “daemon” command).

## Containerization & deployment (demo-oriented)

This repo includes a simple [Dockerfile](../Dockerfile) intended for repeatable demo runs.

Deployment assumptions in this reference implementation:

- Single process, single node (pipeline run writes artifacts into an output directory).
- The API/UI server is a lightweight static+API process that reads those artifacts.
- Horizontal scaling, multi-tenant isolation, and hardened production deployment are out of scope here.

Outputs:

- `events.json`: list of Events and TaskRecommendations
- `audit_log.jsonl`: append-only log of service steps
- Optional: `tasks.jsonl` if `pipeline.export.formats` includes `task_jsonl` and `pipeline.export.task_jsonl.path` is set
- Optional: `events_stix.json` if `pipeline.export.formats` includes `stix`
- Optional: `infrastructure_actions.jsonl` if `pipeline.export.formats` includes `infrastructure`
- Optional: `intents.json`, `playbook_actions.json`, `platform_commands.json`, `assets.json`

Governance controls:

- Configure `pipeline.governance.block_domains` or `pipeline.governance.block_categories` to drop events before decisioning.
- Use `pipeline.governance.severity_caps` (domain -> max severity) to cap event severity without suppressing them.
- Forbidden actions (`pipeline.governance.forbid_actions`) raise and are logged during decisioning.

Human-in-the-loop:

- `pipeline.human_loop.default_require_approval` and `pipeline.human_loop.domain_require_approval` mark tasks as requiring approval.
- `pipeline.human_loop.auto_approve` controls whether tasks that meet approval requirements are immediately marked `approved`.
- `pipeline.human_loop.allow_unsigned_auto_approve` allows the system to approve tasks without a signed token when `pipeline.rbac.min_approvals` is `0`.

Signed approvals (RBAC)

- `pipeline.rbac.approvers` defines approver IDs, shared secrets, and roles.
- `pipeline.rbac.active_approver` / `pipeline.rbac.active_approvers` supply `(id, token)` for a run (CLI can set this via `--approver-id` and `--approver-token`).
- A signed approval token is an HMAC over a message of the form:
	- base task: `<event_id>:<assignee_domain>:<action>:<tenant_id>`
	- infra task: `<event_id>:<assignee_domain>:<infra_action>:<tenant_id>`
- `pipeline.rbac.min_approvals` sets how many signer tokens are required.
- `pipeline.rbac.required_roles` can require specific roles per domain.
- `pipeline.rbac.action_requirements` and `pipeline.infrastructure.action_defaults` can apply per-action requirements (e.g., `lock` requires `sec` role).

Operational note: the default config is intentionally permissive so demos complete without manual token generation. If you want strict signed approvals, set `min_approvals > 0` and disable unsigned auto-approval.

Guardrails:

- `pipeline.guardrails.rate_limits.per_domain` caps tasks per domain per run.
- `pipeline.guardrails.rate_limits.total` caps total tasks per run.
- `pipeline.guardrails.rate_limits.per_event` caps tasks spawned per event.
- `pipeline.guardrails.risk_budgets` caps critical tasks per tenant; overages move tasks to `risk_hold` with exponential backoff (`risk_backoff_base_sec`).
- `pipeline.guardrails.health_alert_drop_ratio` triggers an audit alert when guardrails drop more than the ratio of tasks.
- `pipeline.guardrails.risk_store_path` enables SQLite-backed counters across runs; `risk_window_sec` controls reset window.

Export targets:

`pipeline.export.formats` controls which exports are produced. Supported values in this repo:

- `json`: write `events.json`
- `stdout`: print the export payload
- `metrics`: write `metrics.prom` (Prometheus text)
- `stix`: write `events_stix.json` (STIX 2.1 bundle)
- `task_jsonl`: write approved tasks to JSONL (requires `pipeline.export.task_jsonl.path`)
- `infrastructure`: write simulated infrastructure actions to JSONL (requires `pipeline.export.infrastructure.path`)
- `webhook`: POST the full export payload to `pipeline.export.webhook.url` (optional retries/backoff, optional DLQ)

Infrastructure HTTP forwarding

- `pipeline.export.infrastructure.http` can POST infrastructure actions to an HTTP endpoint. This is optional; by default it is off.
- When enabled and the HTTP send fails, the effector can append the batch to a DLQ file (`pipeline.export.infrastructure.dlq_path`).

Audit log

- Audit entries are hash-chained (`prev_hash`, `hash`) for tamper-evident storage.
- Optional HMAC signing is controlled by `audit.sign_secret`. `audit.verify_on_start` can verify the chain on startup.

Infrastructure scenarios:

- See `examples/scenario_infra.yaml` and `configs/rules.sample.yaml` entries for tailgating, fire alarm, and panic-button events that map to infrastructure tasks (lock/unlock/notify).
