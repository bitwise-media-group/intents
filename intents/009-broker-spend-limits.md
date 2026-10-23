---
id: "009"
slug: broker-spend-limits
title: "Cost-based run budgets and broker-measured usage on every run"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 1
area: broker
effort: high
status: proposed
depends_on:
  - 001-broker-chokepoint
  - 006-durable-records
refs:
  - "https://github.com/devthenet-labs/maul/commit/3f7e18d69b855ba5211b4f10d573be562d4cb27b"
  - "https://github.com/devthenet-labs/maul/commit/e800a6c3e63febf1a2ce1811a8b9dc127ec5ad92"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/pricing.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/budget.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/usageledger.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/usageapi.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/usagemeter"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/usagewire"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/budget-policy.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/sizing.md"
issue: https://github.com/bitwise-media-group/intents/issues/10
---

# [patchy] Cost-based run budgets and broker-measured usage on every run

## What should change, and why?

An operator sets `egressBroker.limits.unit: cost` and caps spend in dollars: per agent pod (`costPerPod`), across the
broker per trailing hour (`costPerHour`), and per run through a budget annotation that only patchy's run controllers may
set. Every settled Investigation and Remediation shows usage as the broker measured it, priced against a named price
table and marked `measured`, `partial` or `reported`. The same figures are written into the run's durable record through
006, so cost survives the Finding's TTL and a broker restart.

001 gives the broker token limits. Token limits count cache reads at full weight and cut long runs early: maul's sizing
notes put 67.7M tokens at about $42. Usage reported by the pod is not trustworthy once repository images (013) control
the CLI, so the trusted figure must come from the broker. Working assumption 3 needs cost in the hard copy, not only in
etcd and broker memory. Findings are the first consumer; intent runs (015 onwards) reuse the same path.

Scope:

- Port from `devthenet-labs/maul@86a3f567^`: `--limit-unit=cost`, `internal/broker/pricing.go`, the reservation and
  shortfall accounting, and `internal/broker/budget.go`. Rename the annotation to
  `patchy.bitwisemedia.uk/budget-micro-usd`. The broker reads it with a UID-checked `get` on the caller pod (a Role with
  `get pods` in the agents namespace only, no `list` or `watch`, rendered only under `unit: cost`).
- Chart values `egressBroker.limits.unit` (`tokens` default, or `cost`), `costPerPod` and `costPerHour` in micro-USD,
  with the token limits kept as optional backstops. `costPerPod` is required with `unit: cost` and refused with
  `unit: tokens`.
- Per-run budgets: investigation-controller and remediation-controller stamp the annotation on each Job and pod template
  from new values `investigationController.config.maxCostMicroUSD` and `remediationController.config.maxCostMicroUSD`.
  The broker holds a pod to the smaller of its budget and `costPerPod`.
- Port `charts/maul/templates/budget-policy.yaml` as a ValidatingAdmissionPolicy: only the run controllers'
  ServiceAccounts may set or change the budget annotation on Jobs and pods in the agents namespace. The chart fails to
  render when `unit: cost` and `admissionPolicy.enabled=false`, or when the cluster is older than 1.30.
- Price table: port `internal/model/measured.go` and the pricing registry, versioned, with an unpriced model charged at
  the dearest rate.
- Measured usage: port `internal/broker/usageledger.go`, `usageapi.go` and `internal/usagewire` (a separate listener and
  token audience), and `internal/usagemeter` in investigation-controller and remediation-controller. Extend
  `UsageSummary` in `api/v1alpha1/common_types.go` with `source` and `measured` (tokens by type, cost, price table
  version).
- Restart safety: at settle the controller writes the broker's per-run total into the run's status. While a run is live,
  its controller also reads the running total from the usage endpoint every 60 s and writes it to
  `status.stage.usage.checkpoint`. On start the broker re-seeds each live pod's ledger from that checkpoint (a read-only
  `get` on investigations and remediations), so a restart no longer resets a pod's spend to zero.
- Records: the 006 Finding adapter adds a `usage` block (source, tokens by type, cost, price table) to each archived
  report. Status is settled first, then the record.
- Cost refusals use the same 429 limit prefix as 001's token refusals, so 001's agent-runner mapping to
  `budget_exceeded` covers them. Extend its tests to cost refusals; do not add a second mapping.
- Docs: `docs/configuration/egress-broker.md` cost limits section and a sizing page adapted from maul.

## How will we know it is done?

- [ ] Ported unit and envtest suites pass: `cost_test.go`, `usageledger_test.go`, `usageapi_test.go` and
      `charts/patchy/budget_policy_envtest_test.go`.
- [ ] e2e: an Investigation with a budget annotation of 1 USD against a fake upstream is refused at the cap, and the
      Investigation records `budget_exceeded`.
- [ ] envtest: a Job in the agents namespace created by any ServiceAccount other than a run controller, carrying the
      budget annotation, is refused by admission.
- [ ] e2e: a settled Remediation shows `status.stage.usage.source: measured` with a price table version, and the
      archived `remediation.md` record holds the same token and cost figures.
- [ ] e2e: the broker is restarted mid-run; the run's measured usage is `partial` and its spend continues from the last
      checkpoint rather than zero.
- [ ] An agent ServiceAccount token gets 401 or 403 from the usage endpoint, and a controller usage token opens nothing
      on the proxy port.
- [ ] Helm render guards: `unit: cost` without `costPerPod`, and `unit: cost` with `admissionPolicy.enabled=false`, both
      fail `helm template` with a message naming the value.

## Isolation invariants

- **No credentials in agent pods:** no pod gains anything. The budget annotation is not a credential, and the VAP stops
  an agent or any other pod creator from raising its own budget. The usage endpoint uses a separate audience that agent
  tokens cannot obtain.
- **Broker-only egress:** unchanged. Spend enforcement happens inside the broker, the only egress path. The broker's new
  `get pods` grant is in-cluster API access, not egress.
- **Custom resources for state, git for artifacts, GitHub as projection:** budgets, measured usage and spend checkpoints
  live on the run custom resources, written by the run controllers; the broker only reads them. The hard copy of each
  run's usage is written to git and blob storage by a controller through 006, never by the pod. The tracking issue may
  show cost as projection only.

## Out of scope

- Attribution of runs to people and usage rollups across runs (021).
- A ledger shared across broker replicas; the broker stays single-replica and the chart says so.
- Intent stage budgets from a Project (015 and 016 reuse this mechanism).
- Live dollar figures on the status page while a run is in flight.

## Depends on

- `001-broker-chokepoint`: the broker enforcement layer, per-pod token limits and the `budget_exceeded` mapping this
  extends to cost.
- `006-durable-records`: the writer and Finding adapter the usage block is archived through.

## References

- `commit 3f7e18d6` feat(broker): cost-weighted limits and per-pod budgets (#229).
- `commit e800a6c3` feat(broker): per-model usage ledger and trusted usage at settle (#227).
- `internal/broker/pricing.go`, `budget.go`, `usage.go`, `usageledger.go`, `usageapi.go`; `internal/usagemeter`;
  `internal/usagewire`; `internal/model/measured.go`.
- `charts/maul/templates/budget-policy.yaml` and `charts/maul/budget_policy_envtest_test.go`.
- `e2e/broker_cost_test.go` and `e2e/broker_cost_openai_test.go`.
- `docs/intents/sizing.md` and `docs/configuration/egress-broker.md`, sections "Cost limits", "Usage endpoint" and
  "Known limitations".

## Open questions

- Broker HA: are run-CR checkpoints enough, or should the ledger move to a shared store so the broker can run more than
  one replica without multiplying limits?
- Who maintains the price table, and how is a vendor price change rolled out: a chart value override, or a patchy
  release?
- Should the default flip to `unit: cost` in a later release, given token limits mis-size cache-heavy runs?
- Is a 60 s checkpoint interval an acceptable worst-case overspend after a restart, or should checkpoints be driven by
  spend deltas?
