---
description: "Model traffic, dependency routes, spend limits, attribution and credentials, through one chokepoint."
---

# Egress broker

The egress broker is the only way out of an agent pod, and the only place a credential is attached to a request. These
intents make it a real chokepoint, then build what depends on it being one. See the
[Isolation model](../concepts/isolation.md).

- **First, close the holes** (001, 002). An allowlist of methods and paths per vendor route; refusal of model vendors'
  server-side tools that reach the internet; pod-bound token checks; per-pod limits. Then codex moves onto the broker
  and copilot is removed, so no agent pod holds a credential.
- **Then measure and bound spend** (009). Cost-based limits per pod, per hour and per run, with usage the broker
  measured written to every run and its record.
- **Then attribute it** (021, 022). Every run is attributed to a verified principal. Usage is reported on the status
  page and through `patchy get usage`, and people can pay for their own runs with their own model keys, which only the
  broker ever sees.
- **Finally, dependencies** (023, 024). Go modules, then npm and PyPI, through authenticated, protocol-aware, read-only
  broker routes with per-run package grants. maul's egress-proxy and CONNECT tunnel are not ported.

--8<-- "build/intent-docs/areas/broker.md"
