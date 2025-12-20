# Operations

This reference repo runs a synthetic scenario through the Helios services.

- `examples/scenario_minimal.yaml` defines a handful of multi-domain readings
- `configs/default.yaml` configures domains, rule thresholds, and export options
- The CLI (`helios_c2.cli`) coordinates the run

Outputs:

- `events.json`: list of Events and TaskRecommendations
- `audit_log.jsonl`: append-only log of service steps
