---
id: "033"
slug: rebrand-api-migration
title: "Rename the product with an in-place, upgradable API group migration"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
  - https://github.com/bitwise-media-group/patchy-app-manifests
phase: 7
area: rebrand
effort: high
status: proposed
depends_on:
  - "010-brand-registry"
  - "005-e2e-agent-pods"
  - "006-durable-records"
  - "027-intents-operator-onboarding"
refs:
  - "https://github.com/devthenet-labs/maul/commit/86a3f567da20960ecd4cf08f6d00f5769eeb6694"
  - "https://github.com/devthenet-labs/maul/commit/55b163a8e8df527e78b9397d1364d385c36d9231"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/groupversion_info.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/common_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnercfg/runnercfg.go"
issue: https://github.com/bitwise-media-group/intents/issues/34
---

# [patchy] Rename the product with an in-place, upgradable API group migration

## What should change, and why?

An operator running patchy can upgrade to the renamed product with `helm upgrade` and one migration command, and keep
every Finding, Intent, Project, Preview, approval and report. Open pull requests, tracking issues, external webhook
senders and dashboards keep working through the change. Two releases carry it. Release N+1 installs the new API group
beside the old one and accepts both sets of names. `<new> migrate` copies every object, with its status, under a global
agent pause. Release N+2 stops reading the legacy names. The new name and API group domain are not chosen here: the
first step of the plan is to confirm them, and the work is otherwise name-agnostic.

Kubernetes cannot rename an API group in place, and several patchy identifiers are external or immutable contracts:
Deployment selector labels (`app.kubernetes.io/part-of: patchy`), the generic webhook headers (`X-Patchy-Signature-256`,
`X-Patchy-Delivery`), the broker header (`X-Patchy-Broker-Token`), sticky-comment markers (`patchy:report`,
`patchy:enrichment`), branch prefixes (`patchy/`, `patchy-intent/`, `patchy-plan/`) and user-written RBAC that names the
group. Each breaks silently if renamed naively. maul renamed patchy to maul (`maul.run`) as a hard cut in commit
86a3f567: its BREAKING CHANGE note says existing installs must delete the release and its CRDs, which deletes all state.
The derivative must not repeat that.

Scope:

- Release N+1, names: set the 010 registry's `Current` to the new names and `Legacy` to patchy's. The dual readers 010
  already built (env prefixes, broker token header, webhook signature and delivery headers, sticky markers, branch
  prefixes, envelope sentinels, finalizers) and its redaction allowlist then accept both without new reader code. This
  intent adds only what 010 leaves out: outbound generic webhook calls send both header sets, new branches use the new
  prefix, and every identifier added after 010 (for example the `patchy-plan/` branch prefix from 017) is confirmed to
  be in the registry.
- Release N+1, CRDs: the chart installs both API groups (legacy CRDs under `crds.keep`), renders RBAC aggregate roles
  and ValidatingAdmissionPolicies for both, keeps selector labels pinned through `brand.legacySelectorLabels`, and
  documents `nameOverride` so `fullname` does not change when the chart name does. Controllers serve the group named by
  `brand.apiGroup`, which defaults to legacy until migration completes.
- `<new> migrate --plan | --export | --apply | --rollback`. `--plan` prints per-kind counts and refuses while agent Jobs
  run, unless given `--wait`. `--export` writes every object as YAML plus a markdown summary and hands both to the 006
  writer as the pre-migration hard copy. `--apply` sets the 027 global agent pause, waits for Jobs to drain, exports,
  then copies every kind the chart installs in dependency order: spec, then status through `/status`, labels,
  annotations and projection hashes re-keyed, and ownerReferences remapped through a UID map. It relabels transcript
  ConfigMaps, verifies counts and spec and status digests per object, flips `brand.apiGroup`, strips legacy finalizers
  and leaves legacy objects as the rollback copy.
- Module path, binaries and packaging: rename the Go module (`pkg/` is an external SDK, so document the move), the
  binaries including `kubectl-patchy` (ship a `patchy` shim and a kubectl plugin alias for one release), images under
  both repositories for one release, the chart names `patchy` and `patchy-config`, the Homebrew cask in
  `bitwise-media-group/homebrew-tap`, the docs site (`site_url` redirects from `oss.bitwisemedia.uk/patchy/`), and
  metrics with a documented dual-emit window.
- `patchy-app-manifests`: publish the OCI artifact under the new name beside `manifests/patchy` for one release, and
  move the seed contract names (`patchy-manifests`, `patchy-vars`, `application-patchy`) with an adoption path so Flux
  does not delete and recreate the release.
- Release N+2: stop reading legacy env vars, headers, sentinels and the legacy group. Keep accepting legacy branch
  prefixes and markers until `<new> migrate --check-github` (read-only) reports no open pull request or tracking issue
  that uses them. Remove legacy CRDs only on explicit operator action.
- Upgrade guide: a pre-flight checklist covering in-flight Jobs, the export, and user RBAC that names the old group.

## How will we know it is done?

- [ ] 010's `TestNoBrandLiterals` and its dual-reader unit tests pass with the real new names as `Current` and patchy as
      `Legacy`, not only with 010's test brand.
- [ ] e2e: a generic webhook signed with the legacy header and one signed with the new header are both accepted, an
      outbound webhook carries both header sets, and the broker accepts an agent request with either token header.
- [ ] e2e `TestRebrandMigration` with the 005 fake kubelet: install release N with Findings in mixed phases (one with an
      open pull request and tracking issue), an Intent with an approved plan, and a Ready Preview. Run `migrate --apply`
      and upgrade to N+1. Assert identical status, no duplicate comments on `e2e/fakegithub`, the open pull request's
      merge settling the migrated Finding, and Deployments keeping their UIDs.
- [ ] e2e: `migrate --rollback` before any new-group write restores service on the legacy group.
- [ ] `migrate --plan` exits non-zero while an agent Job runs, and a test fails if any CRD in the chart is missing from
      the migration order.
- [ ] The `--export` hard copy appears in the 006 fake records target before the first new-group write.
- [ ] Release N+2 passes e2e with legacy readers removed, and `migrate --check-github` lists zero stragglers on the
      fixture.

## Isolation invariants

- **No credentials in agent pods:** no credential is added. During the window the broker accepts two header names for
  the same projected ServiceAccount token. Agents are paused and drained, so no agent runs across the group flip. The
  redaction allowlist and a test keep any `*_TOKEN` or `*_KEY` variable under either prefix out of agent pods.
- **Broker-only egress:** agent NetworkPolicy, broker routes and slot policies are copied, not loosened. The chart
  renders policies for both label sets during the window, and the 003 and 028 probes run against the migrated install.
- **Custom resources for state, git for artifacts, GitHub as projection:** CR state is copied with status, and the
  export lands in git or blob storage before cutover. Migration runs with the operator's kubeconfig and makes no forge
  call except the read-only `--check-github`. GitHub markers are adopted, never read as state.

## Out of scope

- Choosing the new name, domain or API group. This is confirmed as the plan's first step.
- Centralising names in the registry, the dual readers and the redaction allowlist (010). This intent sets their values
  and removes the legacy readers in N+2.
- Renaming GitHub App slugs, external fixture repositories or CHANGELOG history.
- Changing the cluster terraform modules beyond what the `patchy-app-manifests` seed contract needs.

## Depends on

- `010-brand-registry`: every product name behind one Go and Helm registry with current and legacy slots.
- `005-e2e-agent-pods`: running agent Jobs end to end, so migration under pause and drain is tested for real.
- `006-durable-records`: the controller-side writer that archives the pre-migration export.
- `027-intents-operator-onboarding`: the global agent pause and the setup and check commands the upgrade guide uses.

## References

- Commit 86a3f567 (maul's hard-cut rename, with the BREAKING CHANGE note listing every renamed surface) and commit
  55b163a8 (fixture renames) at `devthenet-labs/maul`.
- `api/v1alpha1/groupversion_info.go` and `api/v1alpha1/common_types.go` (group and finalizer constants).
- `internal/runnercfg/runnercfg.go` (`AgentsPausedFlag`, the shared `--agents-paused` switch).
- Pre-rename surfaces at `devthenet-labs/maul@86a3f567^`, which match patchy's: `internal/cli/options.go`
  (`envPrefix = "PATCHY"`), `internal/controller/integration/project.go` (`findSticky`),
  `internal/controller/integration/webhooks.go` (`BranchPrefix`), `pkg/generic/payload.go`,
  `internal/provider/provider.go` (`BrokerTokenHeader`) and `charts/patchy/templates/_helpers.tpl` (`selectorLabels`).

## Open questions

- Should the derivative adopt a name shared with maul, now that maul has renamed itself and moved to `maul.run`? Agree
  this with maul's author before the plan is approved, because it decides whether the module path and API group
  converge.
- Is two releases enough for external webhook senders and downstream SDK users of `pkg/`, or does the legacy-header
  window need a date instead of a release count?
- At about two releases of work plus packaging, does this fit one build? If not, split release N+2 cleanup into its own
  intent.
- Should migration also run as an opt-in Helm hook Job with a scoped ServiceAccount, for GitOps installs that cannot run
  a CLI step?
- Do the cluster modules' generic `modules/application` in `terraform-aws-eks-flux` and `terraform-google-gke-flux`
  embed any of the seed contract names, or only receive them from `patchy-app-manifests`?
