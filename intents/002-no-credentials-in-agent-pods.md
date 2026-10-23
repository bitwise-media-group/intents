---
id: "002"
slug: no-credentials-in-agent-pods
title: "Run every harness through the broker so no agent pod holds a credential"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: broker
effort: medium
status: proposed
depends_on:
  - "001-broker-chokepoint"
refs:
  - "https://github.com/devthenet-labs/maul/commit/efb107c9d42afe2eb169626e7bc7954d15b33475"
  - "https://github.com/devthenet-labs/maul/commit/2a31651f85913d5740d78b41812c3614733d0802"
  - "https://github.com/devthenet-labs/maul/commit/e0f71a26108504b34ff1a2f73de94a46bdad3b8e"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/openai.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/harness/codex.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnercfg/runnercfg.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/codex.md#migrating-from-the-in-pod-key"
issue: https://github.com/bitwise-media-group/intents/issues/3
---

# [patchy] Run every harness through the broker so no agent pod holds a credential

## What should change, and why?

After this lands, no agent pod that patchy creates holds a model key, a forge token or a cloud credential, whichever
runner it uses. That covers `agent.runners` and `evaluationController.runners`. Codex investigations and remediations
reach OpenAI only through a new `/openai` route on the egress broker. The broker holds the OpenAI key in the release
namespace. The copilot runner is removed. A chart render fails if any enabled runner would put a Secret-backed value
into an agent pod. An operator can then state working assumption 1 as a property of the chart, not a convention.

Today `charts/patchy/values.yaml` gives codex `secret: patchy-openai` and `secretEnv: OPENAI_API_KEY`. The key is
injected into the pod through `internal/jobs/jobs.go` `Runner.Secret`, `SecretKey` and `SecretEnv`. Copilot puts a
GitHub token into its pod. The evaluation runners reuse those agent-namespace Secrets. Each is a credential in an agent
pod. They are also why the agent NetworkPolicy still needs TCP 443, which `003-broker-only-agent-network` removes.

Scope:

- Broker: port `internal/broker/openai.go` and the OpenAI half of `dialect.go`. The `/openai` route serves
  `POST /v1/responses` and `GET /v1/models` only, behind the 001 pre-authentication, surface and limits. It allows only
  the hosted tools `function`, `custom`, `local_shell`, `shell`, `apply_patch` and `namespace`. It refuses `background`,
  `previous_response_id`, `conversation`, stored prompts, `file_id` and remote image URLs. It strips
  `OpenAI-Organization` and `OpenAI-Project`, reads usage from terminal events, and answers in the OpenAI error
  envelope. The key is `egressBroker.openaiSecret` in the release namespace.
- Harness: port `codexGatewayConfig` and `codexQuietConfig` from `internal/harness/codex.go`. Codex gets `-c` overrides
  that point a provider with id `patchy` at the broker's `/openai` base URL. The id must not be `OpenAI`: codex then
  zstd-compresses request bodies, which the broker cannot inspect. The placeholder key and the caller-token header are
  passed by env-var name, never on argv. Analytics, plugins and web search are off.
- Re-check every `-c` key at patchy's pin (codex `rust-v0.163.0`). Capture a new request fixture to replace maul's
  `codex-0.153.4-responses-request.json`.
- Provider and runner config: port `provider.CodexEnv` and `CodexGateway`. The codex runner requires `--broker-url`. The
  old codex secret flags and their `PATCHY_` env forms are refused at startup with migration text.
- Jobs: remove the `Runner.Secret*` in-pod credential path from `internal/jobs`. Codex Jobs mount the projected broker
  token like claude Jobs do. If the pinned claude CLI still refuses to start without credentials, brokered claude pods
  get a fixed, non-secret placeholder auth token (commit 5b3bc570). It stays a reserved name that `Config.Env` and
  `Runner.Env` cannot set.
- Copilot: remove the copilot harness, its runner flags, `Dockerfile.copilot-agent-runner`, its chart values and its
  evaluation runner. There is no credible broker route, because its credential is a GitHub token.
- Evaluation runners: `evaluationController.runners.codex` runs brokered or is refused at render and at controller
  startup.
- Render guard: `helm template` fails if any enabled runner, agent or evaluation, would render a `secretKeyRef`, a
  Secret `envFrom` or a Secret volume in `agent.namespace`, other than the per-Job handoff Secret. It also fails, with
  migration text, if `agent.runners.codex.secret`, `secretKey` or `secretEnv` are set.
- e2e fixtures stop creating `patchy-openai` and `patchy-anthropic` in the agents namespace.
- Docs: a codex page with "Turning it on" and "Migrating from the in-pod key". The credential table in
  `docs/deployment/isolation.md` lists no agent-namespace credential.

## How will we know it is done?

- [ ] A golden Job YAML for a brokered codex remediation has no `secretKeyRef` and no `OPENAI_API_KEY`, and it mounts
      the projected broker token.
- [ ] An isolation unit test (a port of `internal/jobs/isolation_test.go`) renders a pod spec for every runner the chart
      can enable. None has Secret-backed env, `envFrom` or a Secret volume except the handoff Secret.
- [ ] Broker unit tests run against a codex `0.163.0` request fixture. The fixture is accepted. A `web_search` tool,
      `previous_response_id`, `background` and a remote `image_url` are each refused with 403 in the OpenAI envelope.
- [ ] An e2e test runs the shipped `egress-broker` with envtest TokenReview and a fake OpenAI upstream. A request with a
      pod-bound token reaches the upstream with the broker's key and without the caller-token header. The audit line
      shows `route=openai` with token counts.
- [ ] `helm template` with `agent.runners.codex.secret` set fails with the migration message. Any `copilot` runner key
      fails with a removal message.
- [ ] Starting remediation-controller with a removed codex secret flag exits non-zero with the migration text.
- [ ] A golden argv test for the codex harness shows provider id `patchy`, web search disabled and no key on argv.

## Isolation invariants

- **No credentials in agent pods:** removes `OPENAI_API_KEY` and the copilot GitHub token, the last credentials in agent
  pods. The OpenAI key moves to a release-namespace Secret that only the broker reads. The placeholder token is a fixed
  public string, and the broker strips it before injecting the real credential.
- **Broker-only egress:** codex model traffic goes only to the broker, which refuses hosted web search and remote
  fetches on `/openai`. The per-runner `hosts` and `dnsPatterns` for `*.openai.com` are no longer needed by any pod.
  Removing TCP 443 and DNS from the agent policy is `003-broker-only-agent-network`.
- **Custom resources for state, git for artifacts, GitHub as projection:** no state model change. Runner choice and
  outcomes stay in Investigation and Remediation status as today.

## Out of scope

- Agent NetworkPolicy, DNS and the sandbox probe (`003-broker-only-agent-network`).
- Cost units and OpenAI pricing (`009-broker-spend-limits`), and per-user OpenAI keys
  (`022-per-user-model-credentials`).
- Codex for intent plan and build stages (`015-intent-stage-runtime`) and codex on repository images (013).

## Depends on

- `001-broker-chokepoint`: the pre-authentication, pod-bound token check, route surface and per-pod limits that the
  `/openai` route sits behind.

## References

- `devthenet-labs/maul@55b163a8`: commits efb107c9 (OpenAI Responses route), 2a31651f (codex through the egress broker),
  e0f71a26 (intents on brokered codex) and 5b3bc570 (placeholder auth token for brokered claude pods).
- `internal/broker/openai.go`, `internal/broker/dialect.go`, `internal/broker/openai_test.go`,
  `internal/broker/testdata/codex-0.153.4-responses-request.json`.
- `internal/harness/codex.go`, `internal/provider/provider.go`, `internal/runnercfg/runnercfg.go`
  (`codexSecretMigration`), `internal/jobs/codex_brokered_test.go`, `internal/jobs/isolation_test.go`.
- `docs/configuration/codex.md`, sections "Turning it on" and "Migrating from the in-pod key".
- `docs/deployment/isolation.md`, section "Credential absence — the real control".

## Open questions

- Copilot: is removal agreed, or must it stay behind an explicit isolation-breaking opt-in that cannot coexist with the
  broker-only defaults in 003? This intent assumes removal.
- The codex evaluation runner image is built in `bitwise-media-group/evolve`. Can it take the broker provider overrides?
  If not, refuse codex evaluations until evolve ships support, and track that in evolve.
- Do the codex `-c` keys (`model_providers.*`, `features.plugins`, `web_search`) still mean the same at `rust-v0.163.0`?
  This needs a probe like `004-claude-posture-hardening` before the pin moves again.
- Does patchy's pinned claude CLI (2.1.304) still need the placeholder token, or has `CLAUDE_CODE_SKIP_*_AUTH` covered
  it?
