---
id: "005"
slug: e2e-agent-pods
title: "Run agent Job pods end to end in e2e with a fake kubelet"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: quality
effort: medium
status: proposed
depends_on: []
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/kubelet_test.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/fakegithub/gitdata.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/fakegithub/checks.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/fakegithub/graphql.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/ports_test.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/hack/fake-agent"
  - "https://github.com/devthenet-labs/maul/commit/6c240132b2c60d005d8dda98904e0eba628ac75a"
issue: https://github.com/bitwise-media-group/intents/issues/6
---

# [patchy] Run agent Job pods end to end in e2e with a fake kubelet

## What should change, and why?

After this lands, `mise run e2e` drives the whole Finding pipeline through patchy's real controller binaries under
envtest. A scanner alert becomes a Finding. An investigation Job's pod runs, and so does the remediation Job's pod. The
changeset is pushed through the Git Data API, a pull request opens on fakegithub, and a merge webhook settles the
Finding as `Remediated`. A fake kubelet runs each Job's pod. The real API server proxies `pods/log` to it, so the
controllers read logs through the clientset with no change. Every later intent can then add an e2e scenario with real
Job pods. That includes the records writer (006), the intent stages (015 to 020), the dashboard (025) and the rebrand
migration (033).

Today patchy's `e2e/pipeline_test.go` stops once the agent Job exists ("no Job ever runs under envtest"). The collect,
transcript, changeset push and pull request leg has never run end to end. `e2e/fakegithub` has Git Data write routes,
but it does not check App permissions per route, it does not serve pushed commits back in tarballs, and it has no
checks, reviews or GraphQL edit history. maul's intent, live output and broker e2e tests all build on its fake kubelet
harness.

Scope:

- Port `e2e/kubelet_test.go` from maul's pre-rename tree under patchy names. It registers Node `e2e-kubelet` with a TLS
  kubelet endpoint, binds and creates pods for Jobs in the agents namespace, and serves `pods/log`. For each run it
  plays the `prepare` init (fetches the artifact from source-controller, checks its digest, writes the per-Job handoff
  Secret into the workspace) and then the agent container. It reports pod and Job status with real exit codes, including
  78 for `003-broker-only-agent-network`.
- Two agent modes. In scripted mode `hack/fake-agent/agent-runner` plays the stage. In brokered mode the kubelet mints a
  pod-bound projected token through TokenRequest and runs the real `agent-runner` binary against the shipped
  `egress-broker` and a fake model upstream. This lets 001, 002 and 009 add Job-level broker scenarios.
- Extend `hack/fake-agent/agent-runner` to emit every patchy stage's `PATCHY-EVENT` envelope for investigate and
  remediate. A fixture selects the outcome, verdict, changeset, usage and failure mode (timeout, budget_exceeded,
  missing report).
- fakegithub, adapted to go-github v93:
  - Check App installation permissions per route, as maul's `handle(pattern, perm, ...)` does, so a missing grant gets
    a 403.
  - Serve tarballs that include pushed commits.
  - Refuse a non-fast-forward `PATCH .../git/refs` with 422 unless `force` is set.
  - Read committed files back through contents and trees.
  - Port checks, reviews, comments and events, GraphQL `lastEditedAt`, and rate-limit headers. The records writer in
    `006-durable-records` needs the commit and ref behaviour.
- Port `e2e/ports_test.go` and the fix from commit 6c240132, so the same free port is never handed out twice.
- A new `TestFindingPipelineFullLeg`, which reuses the `TestPipeline` setup and runs through to the merge.
- Isolation assertions in the harness: every Job it runs has `automountServiceAccountToken: false`, no forge credential,
  and the broker URL. After `002-no-credentials-in-agent-pods` the same check covers every Secret-backed env.
- CI: runs under `mise run e2e` (`hack/e2e.sh`) in the toolchain v3 layout.

## How will we know it is done?

- [ ] `mise run e2e` passes `TestFindingPipelineFullLeg`. A GHAS alert becomes a Finding. The investigation and
      remediation Jobs run on the fake kubelet. A branch `patchy/<finding>` and a pull request appear on fakegithub, and
      the Finding reaches `Remediated` after the merge webhook.
- [ ] In the same test, each run's transcript ConfigMap exists and is readable through the status-server API.
- [ ] A scripted `budget_exceeded` fixture ends the remediation with that outcome, and the Finding follows patchy's
      existing transition for it.
- [ ] A brokered-mode test runs the real `agent-runner` through the shipped `egress-broker` to a fake Anthropic
      upstream. The broker audit line names the pod.
- [ ] A fakegithub unit test: a non-fast-forward ref update is refused with 422, and an installation without
      `contents: write` gets a 403 on `POST .../git/commits`.
- [ ] `TestKubelet` covers pod lifecycle, a digest mismatch in `prepare` failing the init container, and log proxying.
- [ ] The e2e job finishes in CI in under 10 minutes, and `ports_test.go` passes 20 consecutive runs without a flake.

## Isolation invariants

- **No credentials in agent pods:** test-only, and the harness enforces it. Jobs keep the production pod spec. The
  kubelet refuses to run a pod that sets `automountServiceAccountToken: true` or carries a forge credential. The fake
  agent holds nothing. Brokered mode uses only a pod-bound token minted for the run.
- **Broker-only egress:** pods run as local processes, so the harness cannot enforce NetworkPolicy. In brokered mode the
  agent-runner is given only the broker URL and the artifact URL. Policy enforcement is proven by the kind job in 003,
  not here.
- **Custom resources for state, git for artifacts, GitHub as projection:** the full leg asserts state on the Finding and
  run CRs. fakegithub plays the projection and the push target. Its commit and ref behaviour is what the records writer
  in 006 will commit through.

## Out of scope

- Intent-specific e2e scenarios, which come with 015 to 020.
- kind or real-cluster e2e, including the NetworkPolicy proof in 003.
- Running real harness CLIs (claude or codex) in e2e.

## Depends on

- None.

## References

- `devthenet-labs/maul@86a3f567^` (pre-rename names): `e2e/kubelet_test.go` (`brokerToken`, `useAgentRunner`,
  `prepareWorkspace`, `TestKubelet`).
- `e2e/fakegithub/gitdata.go` (`gitRoutes` with per-route permissions), `e2e/fakegithub/checks.go`,
  `e2e/fakegithub/graphql.go`, `e2e/fakegithub/reviews.go`, `e2e/fakegithub/rate.go`.
- `e2e/ports_test.go` and commit 6c240132 (never hand the same free port out twice).
- `hack/fake-agent/agent-runner`.
- `e2e/broker_cost_test.go`, for the shipped broker under envtest TokenReview.

## Open questions

- Should brokered mode be part of this intent, or added by the first broker intent that needs it? It is small, but it
  pulls `egress-broker` into the e2e process set.
- Should the harness also run the evaluation controller's Jobs, or only investigation and remediation for now?
- How much of maul's fakegithub (GraphQL identity, intent permission tests) should be ported now, and how much left to
  the intent intents that use it?
