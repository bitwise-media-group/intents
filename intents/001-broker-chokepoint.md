---
id: "001"
slug: broker-chokepoint
title: "Make the egress broker a model-inference chokepoint, not an open proxy"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: broker
effort: high
status: proposed
depends_on: []
refs:
  - "https://github.com/devthenet-labs/maul/commit/c3a92924085483a8dad5557c8513e320b52785d4"
  - "https://github.com/devthenet-labs/maul/commit/0183d4d2f481ac3dc42bed9b610a0588fae2d847"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/preauth.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/auth.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/surface.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/inspect.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/limits.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/egress-broker.md#enforcement"
issue: https://github.com/bitwise-media-group/intents/issues/2
---

# [patchy] Make the egress broker a model-inference chokepoint, not an open proxy

## What should change, and why?

After this lands, every model request from an existing patchy investigation or remediation pod is checked by the egress
broker before the broker opens any upstream connection. The checks are per-IP pre-authentication, a pod-bound token
check, a fixed list of allowed methods and paths for the route, inspection of the request body, and per-pod limits. A
request that asks the model vendor to fetch a URL, search the web, run code or call a remote MCP server gets a 403. The
Files and Batches APIs get a 404 from the broker itself. A pod over its limit gets a 429, and the run settles with
outcome `budget_exceeded`. Operators can then say that a patchy agent cannot reach the internet, even indirectly through
the model vendor.

Today `internal/broker/server.go` mounts each route as a `/<route>/` subtree and forwards everything after a
TokenReview. `anthropic-beta` passes through untouched. So an agent with no network can still ask the vendor to fetch
the internet for it (`web_fetch`, `web_search`, `code_execution`, `mcp_servers`). That breaks working assumption 2
indirectly, and nothing at the broker bounds what one pod spends. Every later broker intent (002, 009, 021 to 024)
builds on the front end this intent adds.

Scope:

- Pre-authentication: port `preauth.go`. Per-source-IP token buckets, plus a syntactic check that the caller token is a
  projected ServiceAccount token with the broker audience and a `kubernetes.io` pod claim, before any TokenReview.
  Rejections are counted in `patchy.broker.preauth.rejections`.
- Authentication: port the `auth.go` changes. Add a TokenReview rate limiter and a short verdict cache. Require the
  reviewed subject to be `system:serviceaccount:<agent.namespace>:<agent.serviceAccount>`. Require the review's
  `authentication.kubernetes.io/pod-uid` extra to match the token's pod claim.
- Route surface: port `surface.go` for every route patchy has today. That means anthropic (`POST /v1/messages`,
  `POST /v1/messages/count_tokens`, `GET /v1/models`), and the matching invoke paths for bedrock, vertex (pinned project
  and location) and foundry. Any other method or path gets a 404 with no upstream contact.
- Body inspection: port `inspect.go`. Refuse tools whose type starts with `web_search_`, `web_fetch_` or
  `code_execution_`. Refuse top-level `mcp_servers` and `container`. Refuse any `file_id` reference and any non-inline
  content source. Enforce a model allowlist, a `max_tokens` ceiling and the request size cap. Strip denied
  `anthropic-beta` values, in the header and in the body `anthropic_beta` array that bedrock and vertex use.
- Errors: port the Anthropic half of `dialect.go`, so refusals use the Anthropic error envelope. The OpenAI dialect
  comes with `002-no-credentials-in-agent-pods`.
- Limits: port `limits.go` in the token unit only. Per-pod requests, concurrent requests (with the short wait for a slot
  from commit 0183d4d2), tokens per pod, and an hourly token cap across the broker. Cost units and per-run budgets are
  `009-broker-spend-limits`.
- Configuration: `PATCHY_` flags on `cmd/egress-broker`, and chart values `egressBroker.limits.requestsPerPod`,
  `concurrentPerPod`, `tokensPerPod` and `tokensPerHour`, plus `egressBroker.models`, `egressBroker.maxTokens` and
  `egressBroker.betaDenylist`. Ship non-zero per-pod defaults sized from `agent.investigate` and `agent.remediate`
  budgets, not maul's `0` (off).
- agent-runner: map the broker's limit refusal (a 429 with a fixed message prefix) to outcome `budget_exceeded` for
  investigate and remediate, never to a retryable failure.
- Audit and metrics: the audit line gains the refusal reason, endpoint, model and token counts. Port `metrics.go` as
  `patchy.broker.requests`, `patchy.broker.preauth.rejections` and `patchy.broker.tokens`.
- Docs: add an Enforcement section to `docs/configuration/egress-broker.md`. State in `docs/deployment/isolation.md`
  that vendor-side internet tools are refused.

## How will we know it is done?

- [ ] The ported unit tests (`hardening_test.go`, `enforce_test.go`, `routes_test.go`, `inspect_test.go`,
      `limits_test.go`) pass under `github.com/bitwise-media-group/patchy`, with route tables for anthropic, bedrock,
      vertex and foundry.
- [ ] A new e2e test, `TestBrokerEnforcement`, runs the shipped `egress-broker` binary against envtest's TokenReview and
      a fake upstream. A `/v1/messages` body with a `web_fetch_` or `web_search_` tool, an `mcp_servers` block or a
      `file_id` gets a 403 in the Anthropic envelope, and the fake upstream records zero hits.
- [ ] In the same test, `GET /anthropic/v1/files` and `POST /anthropic/v1/messages/batches` return 404 with zero
      upstream hits.
- [ ] In the same test, a token from `kubectl create token` (no pod binding) is refused at pre-authentication.
      `patchy.broker.preauth.rejections` increments and the TokenReview counter does not.
- [ ] A pod-bound token whose pod has been deleted and recreated (UID mismatch) is refused with 401.
- [ ] With `tokensPerPod` set low, the e2e test's second request from the same pod gets a 429 with the limit prefix. An
      agentrun unit test shows that response ending a remediation with outcome `budget_exceeded`.
- [ ] A denied `anthropic-beta` value never reaches the fake upstream, in the header or in the body array.
- [ ] A chart render test pins non-zero default per-pod limits.

## Isolation invariants

- **No credentials in agent pods:** adds no credential anywhere. The broker's RBAC stays `create tokenreviews`. The pod
  UID check uses the TokenReview response, so the broker gets no read access to pods in this intent.
- **Broker-only egress:** closes the indirect path to the internet through the vendor. Server-side web, code and MCP
  tools, Files API references and every upstream endpoint outside the route surface are refused before any upstream
  contact. The broker's own egress (DNS, TCP 443 to model APIs, the API server) is unchanged.
- **Custom resources for state, git for artifacts, GitHub as projection:** no state change. The broker writes nothing to
  Kubernetes. Refusals are audit lines and metrics, and a `budget_exceeded` outcome lands in the run CR as today.

## Out of scope

- The OpenAI Responses route and brokered codex (`002-no-credentials-in-agent-pods`).
- Cost units, per-run budget annotations and measured usage (`009-broker-spend-limits`).
- Per-user credentials, attribution and dependency routes (021 to 024).
- Broker TLS and running more than one broker replica.

## Depends on

- None. This intent applies to patchy's existing Finding pipeline as it stands.

## References

- `devthenet-labs/maul@55b163a8`: commit c3a92924 (route surface, body checks, spend limits and pre-auth) and commit
  0183d4d2 (wait briefly for a concurrency slot).
- `internal/broker/preauth.go`, `auth.go`, `surface.go`, `inspect.go`, `dialect.go`, `limits.go`, `metrics.go`.
- `internal/broker/hardening_test.go`, `enforce_test.go`, `routes_test.go`, `inspect_test.go`, `limits_test.go`.
- `docs/configuration/egress-broker.md`, sections "Enforcement", "Limit flags" and "Known limitations".
- `docs/design/repository-runner-images.md`, section "Broker-side enforcement".
- `e2e/broker_cost_test.go` shows how to drive the shipped broker against envtest TokenReview with pod-bound tokens.

## Open questions

- What should the default per-pod limits be? maul ships `0` (off), and its field notes record a pod passing 5 million
  tokens. Should the render fail when every limit is `0`, unless an operator sets an explicit opt-out?
- Should the model allowlist default to the models in patchy's model registry, or be empty (all models) until an
  operator sets it?
- Which `anthropic-beta` values go on the default denylist? It should cover the Files API, MCP client and code execution
  betas at least. Who keeps it current as Anthropic adds betas?
- The counters live in memory in one replica, so a broker restart resets every pod's totals. Is that acceptable at this
  stage, given `009-broker-spend-limits` adds checkpoints?
