---
id: "010"
slug: brand-registry
title: "Centralise every product name behind a brand registry ahead of a rebrand"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 1
area: rebrand
effort: medium
status: proposed
depends_on: []
refs:
  - "https://github.com/devthenet-labs/maul/commit/86a3f567da20960ecd4cf08f6d00f5769eeb6694"
  - "https://github.com/devthenet-labs/maul/commit/55b163a8e8df527e78b9397d1364d385c36d9231"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/common_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/groupversion_info.go"
issue: https://github.com/bitwise-media-group/intents/issues/11
---

# [patchy] Centralise every product name behind a brand registry ahead of a rebrand

## What should change, and why?

After this lands, every name-bearing identifier in patchy's Go code and charts comes from one place. That is
`internal/brand` for Go and a `_brand.tpl` helper for the `patchy` and `patchy-config` charts. A lint test fails CI on
any brand string literal outside them. Each identifier has a `Current` value and a `Legacy` list. Every reader that
crosses a version or process boundary accepts both. There is no user-visible change in this release: `Current` is
today's name and `Legacy` is empty. Later ports from maul use brand constants, not literals, and the eventual rename
(`033-rebrand-api-migration`) changes one package plus a migration.

A naive rename breaks patchy, and it does so silently. The name appears 5736 times in 616 files, across 138 `PATCHY_*`
env vars. Several of these names are external or immutable contracts:

- the Deployment `selectorLabels` (`app.kubernetes.io/part-of: patchy`), which cannot change in place;
- the generic webhook headers `X-Patchy-Signature-256` and `X-Patchy-Delivery` in `pkg/generic/payload.go`;
- the sticky-comment markers `patchy:report` and `patchy:enrichment`, written as hidden comments in issue comments and
  matched by prefix in `findSticky`;
- the `patchy/` branch prefix in `internal/controller/integration/webhooks.go`;
- `X-Patchy-Broker-Token` and the `PATCHY-EVENT` envelope sentinel.

maul's rename (commit 86a3f567) was a hard cut with no upgrade path. Separately, `credentialNamed` in
`internal/agentrun/agent.go` exempts every `PATCHY_*` variable from transcript redaction. A future
`PATCHY_SOMETHING_TOKEN` credential would leak into transcripts. That is fixed here.

Scope:

- `internal/brand`: one typed registry with `Current` and `Legacy` for each of these:
  - product and binary names (`patchy`, `kubectl-patchy`);
  - the API group `patchy.bitwisemedia.uk`, and the label, annotation and finalizer key prefix;
  - the env prefix `PATCHY`, and the envelope sentinels `PATCHY-EVENT` and `PATCHY-TURN` (plus `PATCHY-OUTPUT` when 015
    adds it);
  - HTTP headers (`X-Patchy-Broker-Token`, `X-Patchy-Signature-256`, `X-Patchy-Delivery`);
  - the command prefix `/patchy`, and the branch prefixes `patchy/`, `patchy-intent/` (reserved for 018) and
    `patchy-plan/` (reserved for 017);
  - comment markers, cookie names (`patchy-auth`, `patchy-auth-provider`) and token audiences;
  - the metric prefix and meter scope names, leader-election IDs, mount paths, default namespaces and Service names, and
    the repository config directory `.patchy/`.
- Wire every use. `internal/cli/options.go` takes `envPrefix` from brand and binds `Current` and each `Legacy` prefix,
  with `Current` winning.
- Dual readers:
  - the broker accepts both token headers, and the generic webhook verifies either signature header;
  - the envelope parser accepts both sentinels;
  - `findSticky` adopts a legacy marker and rewrites it to `Current`;
  - the PR-closed handler resolves both branch prefixes, and finalizer removal handles both keys.
- Kubebuilder markers must stay literal (`+groupName` in `groupversion_info.go`, RBAC markers). The lint test allowlists
  them and checks each one equals `brand.APIGroup`.
- Helm: `_brand.tpl` exposes the same names. `selectorLabels` read `brand.legacySelectorLabels`, so they never change
  when the product name does. Templates use helpers for label keys, annotation keys and the env prefix.
- Redaction: replace the `PATCHY_` prefix exemption in `credentialNamed` with an explicit allowlist of non-credential
  config keys, such as the token-budget numbers.
- Lint: `TestNoBrandLiterals` scans Go string literals with `go/ast` (comments are exempt), chart templates and
  `deploy/kustomize`. It fails with `file:line` on the name outside the registry, the helper, the marker allowlist,
  generated files and the module import path. The module path is renamed last, in 033.
- `AGENTS.md`: new identifiers that carry the product name go through `internal/brand`.

## How will we know it is done?

- [ ] `mise run lint` runs `TestNoBrandLiterals`. Adding `"patchy-foo"` to any package outside `internal/brand` fails
      with its location. A `+groupName` marker that differs from `brand.APIGroup` fails.
- [ ] The full unit, envtest and e2e suites pass. `helm template` output for the default values and for each CI values
      file is byte-identical before and after, and so are the golden Job YAML files.
- [ ] Unit tests with a test brand (`Current: acme`, `Legacy: [patchy]`): - `findSticky` edits a comment headed by the
      legacy `patchy:enrichment x` marker instead of posting a duplicate; - the PR-closed handler resolves a Finding
      from `patchy/<name>` and from `acme/<name>`; - the envelope parser, the broker header check and the generic
      webhook signature check each accept both forms.
- [ ] An options test binds `PATCHY_X` and the test brand's prefix. When both are set, `Current` wins.
- [ ] A redaction test redacts the value of `PATCHY_FAKE_TOKEN` from a transcript and leaves allowlisted budget keys
      alone.
- [ ] A test over every golden agent Job spec finds no env var with a brand prefix whose name contains `TOKEN`, `KEY` or
      `SECRET`.
- [ ] A chart test renders with a different product name and gets identical Deployment `selectorLabels`.

## Isolation invariants

- **No credentials in agent pods:** adds none. The redaction exemption becomes an explicit list, so a brand-prefixed
  credential name is always redacted. A test makes sure no such variable reaches an agent pod.
- **Broker-only egress:** no egress change. Accepting both broker header names carries the same per-Job pod-bound token,
  not a new credential.
- **Custom resources for state, git for artifacts, GitHub as projection:** no API or state change. Comment markers stay
  idempotency keys for the projection, never state. Finalizers are removed under either key, so no object is stuck.

## Out of scope

- Choosing the new name, domain or API group.
- Any visible rename, the API group migration, the module path change, binary shims and docs prose (033).
- Renaming GitHub App slugs, external repositories or published images.

## Depends on

- None.

## References

- `devthenet-labs/maul@55b163a8`: commit 86a3f567 (`chore!: rename patchy to maul`, the hard cut with no upgrade path)
  and commit 55b163a8 (repository and fixture renames). Together they show every surface a rename touches.
- `api/v1alpha1/common_types.go` and `api/v1alpha1/groupversion_info.go`, where the label, annotation, finalizer and
  group names live.
- At `devthenet-labs/maul@86a3f567^` the same files still carry patchy's names, which is useful for diffing which
  identifiers maul added after the fork.

## Open questions

- The new name is not chosen. This intent does not need it, but 033 does. Who decides, and by when?
- Should `Legacy` be fixed at compile time only, or also configurable at runtime for operators who forked the name?
- Metric names: should the registry also plan a dual-emit window now, or leave that to 033?
- Should the lint cover documentation and `CHANGELOG.md`, or only code, charts and kustomize?
