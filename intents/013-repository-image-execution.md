---
id: "013"
slug: repository-image-execution
title: "Run agent stages in the pinned repository image behind trusted injection and admission"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 2
area: runtime
effort: high
status: proposed
depends_on:
  - "012-repository-image-pinning"
  - "003-broker-only-agent-network"
  - "009-broker-spend-limits"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/repository-runner-images.md#pod-construction"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/jobs/jobs.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/preflight.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnerguard"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/sandboxprobe"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/changeset/changeset.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/resourceclass"
  - "https://github.com/devthenet-labs/maul/commit/90a9f9481f843afb88641af5ba7a34fa7193dd07"
issue: https://github.com/bitwise-media-group/intents/issues/14
---

# [patchy] Run agent stages in the pinned repository image behind trusted injection and admission

## What should change, and why?

Once this lands, a Finding remediation for a repository with a pinned image runs in that repository's own toolchain
image, so the agent can run `go test`, `npm test` or `pytest` before it proposes a change. patchy's trusted
`agent-runner` and harness CLI are injected read-only, a strict sandbox probe must pass before untrusted code starts,
and a ValidatingAdmissionPolicy refuses any agent-namespace pod whose images, security context or env do not match what
the job controllers build. A refused, incompatible or unenforced run ends with a named reason on the Finding.

The declared image is untrusted code that controls the process environment, including the loader and libc the CLI runs
on. maul enforces the image choice only in controller code and leaves broker spend limits optional. patchy ports the
execution path with two extra walls: admission-level enforcement of what an agent pod may be, and a render failure
unless broker per-pod spend limits are on. `agent-runner`, the broker and controller-side changeset validation remain
the trust boundaries.

Scope:

- `internal/jobs`: `Spec.RunnerImage` and `Spec.RunnerSearchPath` from `Repository.status.runnerImage`, `Runner.Inject`
  (claude and codex only, set in `internal/runnercfg`), a `patchy-bin` emptyDir that the trusted `prepare` init
  container fills and the agent container mounts read-only at `/patchy/bin`, an absolute command
  `/patchy/bin/agent-runner`, a controller-owned PATH, and the env scrub (loader, shell, git, proxy and every `PATCHY_*`
  key `agentrun.FromEnv` reads that the Job does not set). Agent pods get `automountServiceAccountToken: false` and a
  required ephemeral-storage request and limit. The default-image Job stays byte-identical.
- `jobs.Client.Create` refuses a credentialed runner, a reference not pinned to a digest, and a digest outside
  `agent.repositoryImages.registries` or inside `deny`. It returns the effective `RunnerImageRef`, which is the only
  value written to the `patchy.bitwisemedia.uk/runner-image` and `runner-image-source` annotations and label.
- Strict sandbox probe: on repository-image Jobs the init container runs `agent-runner sandbox-probe` in its strict
  (default) mode after the artifact fetch, and exits 78 if the internet, the API server or the instance metadata
  endpoint is reachable. The collectors already map exit 78 to `SandboxUnenforced` (003). The `--mode=wait` probe on
  default-image Jobs, with `agent.sandboxProbe.onUnenforced`, comes from `003-broker-only-agent-network`.
- `internal/agentrun/preflight.go`: run `/patchy/bin/<cli> --version`, `git --version` and `bash -c true` before the
  stage and emit `image_incompatible` on failure. Resolve the CLI under `PATCHY_BIN_DIR` only (`pinCLI`). The broker's
  limit refusal keeps the `budget_exceeded` mapping from 001 (extended to cost by 009); do not add a second one.
- `internal/runnerguard`: port the kill switch, pull-failure grace, and holding a Finding for a human when it falls back
  to the default image. Extend the breaker that 003 ports (do not port a second one) with maul's repository-image
  fallback: after a trip, repository-image runs fall back to the default image and are held for a human. An `ignore`
  verdict from a repository-image investigation routes to `HandedOff`.
- Port `internal/changeset` with the repository-image rules: an entry cap (`changesetMaxEntries`) and refusal of CI
  paths (`.github/`), `.patchy/` and `.devcontainer/` before any forge call.
- New compared with maul: a ValidatingAdmissionPolicy on Pods and Jobs in `agent.namespace`. The init image must be a
  configured runner image. The agent image must be a runner image, or a digest under `registries` and outside `deny`.
  The securityContext must be uid 65532, read-only root, all capabilities dropped and seccomp `RuntimeDefault`.
  `automountServiceAccountToken` must be false, and no container may use `secretKeyRef`, `envFrom` a Secret or a Secret
  volume. It is bound with `failurePolicy: Fail`.
- New compared with maul: `helm template` fails when `agent.repositoryImages.enabled` is true and the broker's per-pod
  token limits (001) or cost limits (`009-broker-spend-limits`) are zero, or the broker model allowlist is empty.
- Port `internal/resourceclass`: `agent.resources.default` for every agent Job and a validated menu of named classes.
  Picking a class per repository arrives with the intent Project in `018-intent-build-pr`.
- Provenance: the run envelope and run record carry the image digest, its source, the signer key id and the verdict
  timestamp from `012-repository-image-pinning`, for `006-durable-records` to archive.

## How will we know it is done?

- [ ] Golden Job YAML tests: the default-image Job is byte-identical to before. The repository-image Job shows
      `/patchy/bin` read-only, the blanked env, the strict probe, automount off and the ephemeral-storage limit.
- [ ] A preflight unit test with a fake CLI that fails like a musl loader yields `image_incompatible`.
- [ ] An envtest of the admission policy denies a Job whose agent image is an unlisted digest, a tag, a denied prefix,
      or which carries a `secretKeyRef`, and admits the job controllers' own golden Job.
- [ ] An e2e scenario with a Go fixture repository and a locally signed image: the remediation pod runs `go test`, the
      envelope reports the repository image, and the pull request carries the change.
- [ ] An e2e scenario where the changeset touches `.github/workflows/ci.yml` ends `changeset_rejected` with zero forge
      writes.
- [ ] An e2e scenario on a cluster with no NetworkPolicy enforcement ends `SandboxUnenforced` and the agent container
      never starts.
- [ ] A chart render fixture fails with `agent.repositoryImages.enabled: true` and every `egressBroker.limits` value at
      zero, and names the missing value.

## Isolation invariants

- **No credentials in agent pods:** `Create` refuses credentialed runners and the admission policy refuses any
  Secret-sourced env or volume and any mounted ServiceAccount token. The image cannot add a credential, because only
  `/patchy/bin` and controller env reach the process, and the image's ENV was checked for reserved names at pinning.
- **Broker-only egress:** the pod keeps the broker-only NetworkPolicy and DNS posture from
  `003-broker-only-agent-network`. The strict probe proves it per pod before untrusted code runs. Broker per-pod limits
  bound what a hostile image can spend. Package fetching stays off until `023-broker-deps-go`.
- **Custom resources for state, git for artifacts, GitHub as projection:** the effective image is recorded on the
  Investigation and Remediation status and in the run record's provenance, not in an issue comment. Changesets are
  validated by the controller before any forge write.

## Out of scope

- Dependency fetching from a repository image (`023-broker-deps-go`, `024-broker-deps-npm-pypi`). maul's network
  profiles, egress-proxy and CONNECT tunnel are not ported.
- Intent build stages and `IntentRules` (`018-intent-build-pr` reuses this path).
- Evaluation Jobs on repository images, and the copilot harness on any image.
- The agent base image, examples and `patchy init app` (`014-repository-owner-toolkit`).

## Depends on

- `012-repository-image-pinning`: `Repository.status.runnerImage` with a verified digest, search path and signer.
- `003-broker-only-agent-network`: the broker-only NetworkPolicy, DNS isolation and the `sandboxprobe` package with its
  wait mode.
- `009-broker-spend-limits`: broker-enforced per-pod cost limits and measured usage. Through it, 001's per-pod token
  limits and the 429 prefix that agent-runner already maps to `budget_exceeded`.

## References

- `docs/design/repository-runner-images.md`, sections "Pod construction", "Broker-side enforcement" and "Failure modes
  and what the human sees", pinned to `devthenet-labs/maul@55b163a8`.
- `internal/jobs/jobs.go`, `internal/jobs/doc.go`, `internal/runnercfg/runnercfg.go`.
- `internal/agentrun/preflight.go`, `internal/sandboxprobe`, `internal/runnerguard`.
- `internal/changeset/changeset.go`, `internal/resourceclass`.
- `charts/maul/templates/admission-policy.yaml` (no agent-image policy today) and
  `charts/maul/templates/preview-admission.yaml` (the image-pinning pattern to follow).
- Commits `90a9f948` (Jobs and agent-runner), `b00856d4` (job controllers), `f78e0b22` (chart and broker limits),
  `80861028` (held default-image fallbacks).

## Open questions

- Should a Finding whose pinned image fails preflight or pull fall back to the default image, or always be held for a
  human? maul holds after fallback; patchy could refuse fallback entirely.
- Should codex be injected for repository-image remediations now, or only claude until codex's read-only posture is
  enforced by more than the prompt?
- Is a startup canary Job (probe only) required before the first repository-image Job, as maul's design suggests, or is
  the per-pod strict probe enough?
- Run records will contain CLI-reported usage that the image controls. Should the run record take token and cost totals
  only from the broker's per-pod accounting for repository-image runs?
- After a breaker trip caused only by a repository-image Job, may default-image Jobs resume, or does 003's rule (no new
  agent Jobs until restart) still apply to them?
- Does the admission policy need a break-glass exemption for operator debugging pods in the agent namespace, or must
  debugging happen elsewhere?
