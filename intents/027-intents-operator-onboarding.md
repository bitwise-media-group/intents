---
id: "027"
slug: intents-operator-onboarding
title: "Take an operator from nothing to a Ready intent Project with setup and check commands"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
  - https://github.com/bitwise-media-group/patchy-app-manifests
phase: 5
area: ux
effort: high
status: proposed
depends_on:
  - "018-intent-build-pr"
  - "014-repository-owner-toolkit"
  - "006-durable-records"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/setup.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/ghapp"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/intentperm"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/projectcheck"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul-config/templates/projects.yaml"
  - "https://github.com/devthenet-labs/maul/commit/707019c065887359b2a796c6266f2fb88e826c32"
  - "https://github.com/devthenet-labs/maul/commit/cf5b9640adf90651b996fbefc6118f88ee7d30cb"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/deploying.md"
issue: https://github.com/bitwise-media-group/intents/issues/28
---

# [patchy] Take an operator from nothing to a Ready intent Project with setup and check commands

## What should change, and why?

After this lands, an operator with a cluster, Helm and their own `GH_TOKEN` can follow one documented path to a Ready
intent Project and check every step:

1. `patchy setup github-app --org <org> --intents` creates a GitHub App with exactly the grants intents need, and writes
   a Secret manifest ready for sops.
2. The `patchy` chart, with `intentController.enabled` and `records.*`, plus the `patchy-config` chart with a `projects`
   entry, renders a Project whose intents come from a path in a git repository.
3. `patchy init app` (from 014) scaffolds the application repository's agent image.
4. `patchy check project <name>` prints PASS or FAIL for each readiness item, and exits non-zero on any FAIL.
5. One switch, `agent.paused`, stops all new agent Jobs across the cluster without losing queued work.

The platform clusters get the same setup through `patchy-app-manifests`. Docs, metrics and optional alerts cover running
it.

maul's intents became usable by other teams only once these tools existed. Its `FIELD-NOTES.md` records the friction of
onboarding without them. maul's versions assume GitHub issues as intake: labels, issue permissions, and readiness that
checks labels. patchy needs them rewired to git as the record (working assumption 3), with a private records repository
(working assumption 4) and the broker-only posture checked as part of readiness. Kustomize drifted behind Helm in maul
without anyone deciding it should. Here that drift is decided and documented. `033-rebrand-api-migration` needs the
global pause to drain agents before it flips API groups.

Scope:

- `patchy setup github-app [--intents] [--checks] [--dry-run]`: port `cmd/maul/internal/ghapp` (manifest, loopback
  callback, code exchange, Secret output) and `setup.go` to `cmd/patchy/internal/ghapp`. Permissions come from a port of
  `internal/intentperm`, rewritten for git intake:
  - the intents repository: `contents: read`;
  - the records repository: `contents: write`;
  - application repositories: `contents: write` and `pull_requests: write`, plus `checks`, `statuses` and `actions` read
    for check-fix;
  - `issues: write` only when the GitHub projection is on.
- `patchy check project <name> -n <ns>`: port `cmd/maul/internal/projectcheck` and `checkproject.go`. It checks:
  - the Project exists and is Ready;
  - the App is installed on every repository;
  - each repository's grants match `intentperm`, proven by minting a single-repository installation token with exactly
    those grants (commit cf5b9640);
  - `Project.spec.intents` names a path that exists on its branch and holds files that pass the `007-artifact-contract`
    validator;
  - each application repository has an accepted, pinned image (`Repository.status.runnerImage`), reported with the same
    checks `patchy check image` runs (012, 014), not a second implementation;
  - the records repository is writable and private, unless `records.allowPublic` is set;
  - the posture is broker-only: the agent NetworkPolicy and `dns: none` are present and the sandbox breaker is not
    tripped;
  - at least one brokered runner is enabled. Preview checks are `032-preview-setup-check`.
- `patchy-config`: port `charts/maul-config/templates/projects.yaml` to render `Project` CRs with
  `spec.intents {repository, path, branch}`, `spec.repositories` and `spec.approvers` as defined by 016 and 017, with a
  values schema. The render fails on a Project with no intents path.
- `patchy` chart: `agent.extraEnv` and `agent.extraVolumes` for controllers (commit 707019c0). Document the `records.*`
  values from 006 next to `intentController.*`.
- Global pause: port `RegisterAgentsPausedFlag` (`--agents-paused`) to investigation, remediation, intent and evaluation
  controllers. Chart value `agent.paused`. While paused, schedulers grant no slot. A run granted just before the pause
  does not launch. Held runs carry condition `AgentsPaused`. Running Jobs finish and are collected. status-server shows
  the pause to signed-in users only.
- Kustomize: add `intent-controller` and `status-intents` components. `docs/deployment/kustomize.md` states that
  kustomize covers the core pipeline and intents, and lists Helm-only features (previews, per-user credentials).
- Observability: metrics `patchy.intent.phase_transitions`, `patchy.intent.approval_latency`, `patchy.intent.rounds` and
  `patchy.records.write_failures`. An optional `PrometheusRule` (`monitoring.alerts.enabled`) alerts on records write
  failures, a tripped sandbox breaker, agents paused for longer than a set time, broker spend burn, and intents stuck in
  a phase.
- Docs: `getting-started/intents.md`, `intents/deploying.md` (no AWS terraform module), `intents/onboarding-app.md`,
  `intents/sizing.md`, and generated CLI reference pages for `setup` and `check`.
- `patchy-app-manifests`: enable intent-controller in `manifests/deploy/common`, with the App Secret synced per cloud
  (`resourceset-secrets.yaml` under `aws` and `google`). Add `patchy-vars` keys for the records repository and bucket,
  and the bucket grants in `modules/aws` and `modules/google`.

## How will we know it is done?

- [ ] `patchy setup github-app --org acme --intents --dry-run` prints the App manifest. A golden test pins its
      `default_permissions` to the `intentperm` table.
- [ ] e2e on the 005 harness: `patchy check project shop -n patchy` prints PASS for every item on a configured Project.
      Removing `contents: write` from the records repository installation in fakegithub makes it exit 1 with a FAIL line
      naming the repository and the missing grant.
- [ ] `patchy check project` prints FAIL when the records repository is public and `records.allowPublic` is false, and
      when the agent NetworkPolicy allows TCP 443.
- [ ] A chart envtest test: `helm template` with `intentController.enabled` and a `projects` entry renders a Project CR
      that passes server-side CRD validation. A Project without an intents path fails the render.
- [ ] e2e: with controllers started with `--agents-paused`, a queued Finding and an approved intent create no Job and
      carry `AgentsPaused`. A Job already running completes and is collected. Unpausing launches the queued runs in
      order.
- [ ] CI builds `kubectl kustomize deploy/kustomize/overlays/dev` with the `intent-controller` component.
- [ ] The new metrics appear in an OTel file-exporter test. With `monitoring.alerts.enabled=true` the chart renders a
      `PrometheusRule` that passes `promtool check rules`.
- [ ] `mise run docs` builds the site with the new pages and no broken links.
- [ ] In `patchy-app-manifests`, `kustomize build` of `manifests/deploy/aws` and `manifests/deploy/google` renders
      intent-controller enabled with the App Secret sync, and that repository's CI passes.

## Isolation invariants

- **No credentials in agent pods:** the CLI commands run on the workstation with the operator's own `GH_TOKEN`, AWS
  chain and docker keychain. They never read a cluster Secret. The App private key goes to stdout or a file for sops,
  and only into the release namespace. Tokens minted by `check project` are used for read-only checks and then
  discarded. The render guard from 002 still fails if any runner would get a credential.
- **Broker-only egress:** the chart keeps agent policies naming only the broker and the artifact server, and ships no
  egress-proxy or network-profile templates. `check project` fails a Project whose cluster has lost the broker-only
  posture. The pause switch changes scheduling only.
- **Custom resources for state, git for artifacts, GitHub as projection:** Projects point at a git intents path and a
  private records repository, and readiness checks both. `issues: write` is granted only for the projection. Labels are
  not a readiness item, unlike in maul. The pause is a flag and a condition on held runs, not a GitHub fact.

## Out of scope

- `patchy setup previews` and `patchy check previews` (`032-preview-setup-check`).
- `patchy init app` and `patchy check image` themselves (`012-repository-image-pinning` and
  `014-repository-owner-toolkit`). This intent documents them and reuses the image check per repository.
- The `deploy/terraform/aws` reference module, egress-proxy templates, and the dashboard and actions (025, 026).

## Depends on

- `018-intent-build-pr`: the end-to-end intent loop (plan, approve, build, pull request) that a Ready Project turns on,
  and the application repository grants it needs.
- `014-repository-owner-toolkit`: `patchy init app` and `patchy check image`, which the onboarding docs walk through.
- `006-durable-records`: the `records.*` configuration and the records repository that readiness checks.

## References

- `devthenet-labs/maul@55b163a8`: `cmd/maul/internal/cli/setup.go`, `cmd/maul/internal/ghapp`,
  `internal/intentperm/intentperm.go`, `cmd/maul/internal/projectcheck`, `cmd/maul/internal/cli/checkproject.go`.
- `charts/maul/templates/intent-controller.yaml`, `charts/maul-config/templates/projects.yaml`,
  `deploy/kustomize/components/intent-controller`, `deploy/kustomize/components/status-intents`.
- `internal/runnercfg/runnercfg.go` (`AgentsPausedFlag`, `RegisterAgentsPausedFlag`).
- Commits 707019c0 (extra env and volumes, global agent pause), cf5b9640 (prove check-fix read permissions before a
  Project is Ready), 026faf03 (check project) and e54150cc (sizing guide).
- `docs/getting-started/intents.md`, `docs/intents/deploying.md`, `docs/intents/onboarding-app.md`,
  `docs/intents/sizing.md`, `FIELD-NOTES.md`.

## Open questions

- Kustomize: is "core pipeline plus intents, with Helm-only features listed" acceptable, or is full parity required?
- `check project` proves grants by minting tokens, which needs the App private key on the workstation. Should it fall
  back to the Project conditions the controllers set, when the key is not at hand?
- Approvers: GitHub logins, Kubernetes subjects, or both? This must match `017-intent-approval`.
- The global pause is useful for Findings today, and 033 needs it. Should it move into a small earlier intent instead of
  waiting for phase 5?
- Should the `PrometheusRule` ship in the chart, or only as documented examples?
- Which platform cluster turns intents on first in `patchy-app-manifests`, and who provisions its records bucket?
