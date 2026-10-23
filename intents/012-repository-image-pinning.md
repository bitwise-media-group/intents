---
id: "012"
slug: repository-image-pinning
title: "Resolve, verify and pin repository-declared agent images in source-controller"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 2
area: runtime
effort: high
status: proposed
depends_on:
  - "005-e2e-agent-pods"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/repository-runner-images.md#resolution-and-pin-once-recording"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/repository-runner-images.md#operator-policy"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnerimage"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnerimage/resolve"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/source/repository_controller.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/imagecheck"
  - "https://github.com/devthenet-labs/maul/commit/69469434d08842c1dc72ac5c1ad74f12bee183b8"
issue: https://github.com/bitwise-media-group/intents/issues/13
---

# [patchy] Resolve, verify and pin repository-declared agent images in source-controller

## What should change, and why?

Once this lands, an application repository can name the image its agent should run in, and an operator can see, on the
Repository custom resource, exactly which signed digest patchy accepted for it, or a readable reason why it was refused.
A repository declares its image in `.patchy/agent.yaml` (one key, `image`), or as the top-level `image` of
`.devcontainer/devcontainer.json`. source-controller reads the declaration from the tarball it has already pinned,
resolves the reference once to a digest, checks it against operator policy and a cosign signature, and records the
result on `Repository.status.runnerImage` beside `status.resolvedSHA`. A repository owner can run
`patchy check image <ref>` on a workstation and get the same verdicts from the same code.

Agents cannot build or test an application without its toolchain, and agent pods have no network to fetch one. Pinning
the image once, by digest, against an allowlist and a required signature is the supply-chain half of running agent
stages in an application-declared image. Nothing runs in the image yet: execution is `013-repository-image-execution`.
Resolution needs registry credentials, so it stays in the controller tier and never happens in an agent pod.

Scope:

- Port `internal/runnerimage` from maul's pre-rename tree under patchy names: the `.patchy/agent.yaml` strict parser
  (unknown keys refused, 64 KiB cap, no `build:`), the JSONC devcontainer judge (build, features, variable substitution
  and parse errors are "not applicable", not a rejection), precedence (`.patchy/agent.yaml` wins and never falls through
  when invalid), the `Policy` allowlist and deny list with segment-boundary matching, the PATH sanitiser, and the
  reserved ENV and VOLUME checks. Reserved ENV uses `PATCHY_*` in place of `MAUL_*`.
- Port `internal/runnerimage/resolve`: a single HEAD to pin a tag, every later call by digest, enumeration of each
  `linux/amd64` and `linux/arm64` child of an index, a compressed-size cap per child, a host-selected keychain (ECR
  helper, Artifact Registry ADC, mounted dockerconfigjson, anonymous last), in-process cosign key verification of bundle
  v0.3 referrers and the legacy `.sig` tag, and a digest-keyed verdict cache that never caches the tag HEAD. This
  promotes `internal/mirror/imageref` and `internal/mirror/ocireg` to a controller consumer.
- API: add `RunnerImage` status (`declared`, `manifest`, `image` as `name@sha256:...`, `searchPath`, `verified`,
  `signer` key id and signature form, `resolvedAt`, `message`), the `RunnerImageResolving`, `RunnerImageRejected` and
  `RunnerImageResolveFailed` reasons, and a two-phase status write in the Repository reconciler so a registry outage
  never forces a tarball re-download. `stall(reason)` keeps the artifact so a rejected Repository still has a tree.
- Pin once: a Repository with `status.runnerImage` set is never resolved again, so a moved tag cannot change the
  environment between investigation and remediation of one Finding.
- Chart: `agent.repositoryImages` with `enabled` (the kill switch, default false), `registries` (required when enabled),
  `deny`, `cosignPublicKey` (required when enabled, PEM-validated at render), `maxBytes`, `onReject`, `pullSecret` and
  `pullSecretData`. There is no `allowUnsigned` value in patchy. Render fails when enabled with
  `agent.networkPolicy.create: false` or when `agent.networkPolicy.broadEgress` resolves to broad.
- CLI: add the `patchy check` command group and `patchy check image <ref>`, which runs the resolver's checks with the
  caller's own registry credentials and prints one PASS or FAIL line per check, with `-o json`. The `--run` flag that
  runs the image is added by `014-repository-owner-toolkit`.
- Docs: the image contract for repository owners (glibc, `bash`, `sh` and `git` on PATH, readable by uid 65532, no
  VOLUME, no reserved ENV, dependencies baked in) and an operator page for `agent.repositoryImages`.

## How will we know it is done?

- [ ] `internal/runnerimage` table and property tests pass: normalisation is idempotent, `ghcr.io/org/` never matches
      `ghcr.io/org-evil/x`, a sanitised PATH never has an empty component, and a reserved-ENV fixture is rejected.
- [ ] An in-process registry test flips a tag between the HEAD and the config fetch and asserts that the recorded digest
      is the one every check ran against.
- [ ] Signature fixtures in both forms verify. An unsigned image and one signed with another key are each rejected with
      `RunnerImageRejected` and a message naming the cause.
- [ ] An envtest shows the two-phase write: `resolvedSHA` persists with `Ready=False/RunnerImageResolving` while the
      registry fails, and `runnerImage` is written once with `Ready=True` when it recovers.
- [ ] An e2e scenario with a local registry: a repository with `.patchy/agent.yaml` gets `status.runnerImage.image`
      pinned to `@sha256:` with `verified: true`; a repository whose devcontainer builds its image keeps the default
      image and records a "not applicable" message.
- [ ] `helm template` fails with `agent.repositoryImages.enabled: true` and no `cosignPublicKey`, and fails when
      `broadEgress` resolves to broad. A render with `allowUnsigned` set fails as an unknown value.
- [ ] `patchy check image` prints a FAIL line for each of a disallowed registry, an unsigned image and an image that
      declares a VOLUME, and exits non-zero.

## Isolation invariants

- **No credentials in agent pods:** registry credentials live only in source-controller (the mounted dockerconfigjson or
  workload identity) and in the kubelet's pull path. The agent ServiceAccount's `imagePullSecrets` entry is consumed by
  the kubelet and never mounted or exposed as env in a pod.
- **Broker-only egress:** no agent pod contacts a registry. Resolution runs in source-controller, which already has
  forge egress; the render guards keep repository images off any install where agent pods have broad egress.
- **Custom resources for state, git for artifacts, GitHub as projection:** the declaration is read from the pinned git
  tarball with no second forge call. The verdict lives on `Repository.status`. Signer and digest are recorded so
  `006-durable-records` can copy them into the run record. Any issue comment about a rejection is a projection only.

## Out of scope

- Running anything in the pinned image, injection, admission policy and the strict sandbox probe
  (`013-repository-image-execution`).
- Keyless (Fulcio and Rekor) verification, and building images from a Dockerfile or devcontainer features.
- The guard that keeps the agent allowlist disjoint from a preview image prefix. The `deny` list lands here; the chart
  check against the preview prefix lands with `030-preview-image-supply`.
- Evaluation Jobs, which have no pinned tree and keep the per-harness runner image.

## Depends on

- `005-e2e-agent-pods`: an e2e harness that runs real agent Job pods, so the local-registry scenario can assert what a
  Repository pins end to end.

## References

- `docs/design/repository-runner-images.md`, sections "The declaration file and precedence", "Resolution and pin-once
  recording" and "Operator policy", pinned to `devthenet-labs/maul@55b163a8`.
- `internal/runnerimage` and `internal/runnerimage/resolve` (signature fixtures in `resolve/testdata`).
- `internal/controller/source/repository_controller.go` and `api/v1alpha1/repository_types.go`.
- `charts/maul/templates/_helpers.tpl`, `maul.repositoryImagesGuard`.
- `cmd/maul/internal/cli/check.go` and `cmd/maul/internal/imagecheck` (`cmd/patchy/...` at `86a3f567^`).
- `docs/configuration/source-controller.md` and `docs/deployment/isolation.md#repository-declared-images`.
- Commits `0949aed2` (API types), `00e1e5ee` (pure core), `69469434` (source-controller pinning), `b4c563af`
  (`check image`).

## Open questions

- Should `onReject` default to `handoff` in patchy, so a rejected declaration parks the Finding for a human instead of
  silently running on the default image?
- Is the devcontainer fallback wanted at all, or should patchy honour only `.patchy/agent.yaml` so every repository opts
  in explicitly?
- One operator key or several: should `cosignPublicKey` become a list, so each application team can sign with its own
  key under its own allowlist prefix?
- maul deferred a startup canary and keyless verification (design Decision 5). Which of these must ship before
  repository images are enabled for third-party application repositories rather than operator-owned ones?
- Should the pin be re-evaluated when the operator rotates the cosign key, or does pin-once hold until the next
  Repository is created?
