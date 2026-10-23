---
id: "020"
slug: intent-multi-repo
title: "Plan once and build across several repositories for one intent"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: high
status: proposed
depends_on:
  - 019-intent-review-rounds
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_siblings.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_untracked.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/multirepo_rounds_property_test.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/trees.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/intent_siblings.md.tmpl"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/intentrun_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/intent_multirepo_test.go"
  - "https://github.com/devthenet-labs/maul/commit/76e6ac9cb177d3d8bd0c75b59075951b3ed2295e"
  - "https://github.com/devthenet-labs/maul/commit/2c1bd4fc3531fef4fcdc05408ca8014cd2d89180"
  - "https://github.com/devthenet-labs/maul/commit/12c2fde6dff073315b471744ac46f40a6d1a0d77"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#slice-3-multi-repo-intents"
issue: https://github.com/bitwise-media-group/intents/issues/21
---

# [patchy] Plan once and build across several repositories for one intent

## What should change, and why?

After this lands, one intent can change several repositories, for example an API, its frontend and its infrastructure.
With `--intent-multi-repo` on, a `Project` may list up to 8 repositories. One read-only plan run reads every repository
as a tree and names the subset it will change. The plan states the contracts between those repositories once, and one
approval covers all of them. Each named repository then gets its own build in its own accepted image and its own pull
request. The Intent reaches `InReview` only when every pull request is open, and `Merged` only when every one has
merged.

Real features often span repositories, and maul proved this design in use. It stays behind a flag so it ships only after
the single-repository path is stable, and turning the flag off is a real rollback.

Scope:

- Lift the one-repository limit on `Project.spec.repositories` to 8 when `--intent-multi-repo`
  (`PATCHY_INTENT_MULTI_REPO`) is on. With it off, a Project listing several repositories leaves its Intents `Blocked`
  with `UnsupportedRepositories` and creates no run. Turning it on again resumes them.
- Plan: port `IntentRun` `spec.trees` and `status.trees`. One plan run receives every repository as a digest-verified
  tree from source-controller (extra `Repository` objects owned by the run) through the `internal/agentrun/trees.go`
  fetch path. `ParsePlan` requires `repositories` to be a non-empty subset of the Project's, and the plan template asks
  for the cross-repository contracts in one section.
- Approval is unchanged: one plan record commit and one `planDigest` cover every repository. Record the approved,
  ordered repository list on `status.approval`.
- Build: one build `IntentRun` per approved repository, each in that repository's accepted image from
  `013-repository-image-execution`, each with its own `patchy-intent/<intent>` branch and pull request. All builds share
  the intent Job slot pool.
- Pull requests and endings: port `intent_siblings.go` so each pull request gets a sibling cross-link notice. Keep
  `InReview` until all are open. `Merged` requires every pull request merged. `Closed` lists which merged and which did
  not.
- Rounds: serialise rounds per Intent, each scoped to one repository, with checks observed per pull request.
- Departed repositories and deleted Projects: port `intent_untracked.go` and the follow-ups in commit `12c2fde6`. A
  repository removed from the Project mid-review gets no further writes, while the other pull requests continue. Block
  on `RepositoryKeyChanged` when a repository's identity changes.
- Prove the `intentperm` grants for every listed repository before `Ready`.
- Records: one build run record per repository (`runs/<run>.md`, the run name carrying the repository key) and a
  `summary.md` listing every pull request, through `006-durable-records`.

## How will we know it is done?

- [ ] A ported `e2e/intent_multirepo_test.go` with git-native intake: a two-repository plan, two builds, two pull
      requests, sibling cross-links, both merged, then `Merged`. Both build records and the summary verify.
- [ ] A plan naming a repository outside the Project is refused before it is offered for approval.
- [ ] With the flag off, a Project with two repositories leaves its Intent `Blocked` with `UnsupportedRepositories` and
      no `IntentRun`. With the flag on again, the Intent resumes.
- [ ] The Intent stays `Building` while one of two builds is still running, and enters `InReview` only when both pull
      requests are open.
- [ ] A repository removed from the Project mid-review gets no further GitHub write, and rounds on the other pull
      request continue.
- [ ] The seeded property test for round serialisation (`multirepo_rounds_property_test.go`, ported) passes.
- [ ] A Project listing 9 repositories is refused by CRD validation.

## Isolation invariants

- **No credentials in agent pods:** the plan pod reads every tree as a digest-verified tarball from the artifact server,
  with no forge access. Each build pod is brokered and holds no credential. Tokens are minted by intent-controller for
  exactly the one repository being written.
- **Broker-only egress:** unchanged per pod. More trees mean more artifact fetches from the in-cluster artifact server,
  not new destinations.
- **Custom resources for state, git for artifacts, GitHub as projection:** per-repository runs, pull requests and checks
  live on `Intent` and `IntentRun` status. One approval digest covers all repositories, so each build receives exactly
  the approved plan, and each build has its own git record.

## Out of scope

- Multi-component previews (`031-preview-intent-projection` and the previews area).
- Atomic merge across repositories, and merge ordering between them.
- More than 8 repositories per Project, or repositories on more than one forge.

## Depends on

- `019-intent-review-rounds`: rounds and limits for one pull request, which this intent serialises across several.
  Through its chain, the plan, approval and build paths from `016-intent-planning`, `017-intent-approval` and
  `018-intent-build-pr`.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/controller/intent/intent_siblings.go`, `intent_untracked.go`, the
  multi-repository branches of `intent_plan.go`, `intent_build.go`, `intent_revise.go`, `run_controller.go`.
- `api/v1alpha1/intentrun_types.go` (`spec.trees`, `MaxIntentRunTrees`), `internal/agentrun/trees.go`.
- `internal/templates/intent_siblings.md.tmpl`, `e2e/intent_multirepo_test.go`,
  `internal/controller/intent/multirepo_rounds_property_test.go`.
- Commits `76e6ac9c` (slice 3 wave A), `2c1bd4fc` (slice 3 wave B), `12c2fde6` (departed repositories and deleted
  Projects).
- `docs/design/intent-driven-development.md#slice-3-multi-repo-intents`.

## Open questions

- When one repository has no accepted image, should the whole intent block before any build, or should the other builds
  proceed?
- Should a plan be allowed to name repositories it only reads, so reviewers see why they were included?
- Should sibling cross-links point at the git records as well as the other pull requests?
- Is per-intent cost (`maxCostMicroUSD`) still per intent, or should multi-repository intents get a per-repository
  share?
