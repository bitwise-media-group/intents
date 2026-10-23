---
id: "007"
slug: artifact-contract
title: "Define the git artifact contract for intents, plans and run records, with a validator"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
  - https://github.com/bitwise-media-group/intents
phase: 1
area: records
effort: medium
status: proposed
depends_on: []
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/plan.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/visible.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/text.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/build.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/intent_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#plan-contract-and-output-sanitisation"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#ending-an-intent-and-its-name"
issue: https://github.com/bitwise-media-group/intents/issues/8
---

# [patchy] Define the git artifact contract for intents, plans and run records, with a validator

## What should change, and why?

A person or an agent can write an intent request in git, run `patchy lint intents <dir>`, and know before any controller
exists that the request, and any plan, approval or run record beside it, matches the contract patchy's controllers will
read and write. An intents repository can call a reusable GitHub workflow that runs the same check on every pull
request. This repository adopts it first.

Working assumption 3 moves requests, plans, approvals and run records into git. That only works if the bytes have one
agreed shape: the planner reads the request, the approver reads every byte of the plan, and the build receives exactly
the approved plan. maul has a strict plan contract (`internal/report` `ParsePlan`, visible-text and layout rules), but
its request is a GitHub issue body and its identity is the issue number. This intent fixes the git-native shape and
identity once, so 006, 015, 016, 017 and 021 build on the same contract instead of each inventing one.

Scope:

- Versioned schemas, as JSON Schema files under `schemas/artifacts/v1/` in patchy, with matching Go types and parsers in
  a new public package `api/artifacts/v1` (the schemas embedded), so the skills plugin and other repositories can use
  them:
  - **Request** (`request.md`): frontmatter `id`, `slug`, `title`, `project`, `repositories`, optional `depends_on`,
    `effort` and `status`, plus extension keys a repository declares. The body is an H1 `# [<project>] <title>` matching
    the frontmatter, then `What should change, and why?` and `How will we know it is done?`, then optional
    `Isolation invariants`, `Out of scope`, `Depends on`, `References` and `Open questions`, in that order.
  - **Plan** (`plan-r<N>.md`): maul's `ParsePlan` frontmatter (`summary`, `repositories`, `new_dependencies`,
    `questions`, `confidence`, `estimated_max_turns`, `estimated_token_budget`) and its bounds, ported from
    `devthenet-labs/maul@86a3f567^`, plus the plan body rules.
  - **Approval** (`approval-r<N>.md`):
    `{intent, planRevision, repository, commit, path, blobSHA, sha256, requestSHA256, by, source, at}`, where `source`
    is one of `review`, `cli`, `status-page` or `command`.
  - **Run record** (`runs/<run>.md`): the report plus provenance frontmatter: run name, stage, harness, model, image
    digest and source, base SHA, plan digest, changeset digest, outcome, and a `usage` block with `source` (`measured`,
    `partial` or `reported`), tokens by type, cost in micro-USD and the price table version.
- Repository layout v1: `<project>/<id>/request.md`, `plan-r<N>.md`, `approval-r<N>.md` and `runs/<run>.md`. Only the
  request is human-authored; the rest are controller-written.
- Identity: the stable `id` in the request frontmatter is the intent's identity, unique within the repository, equal to
  its directory name and immutable once merged. The Intent custom resource is named `<project>-<id>`. The issue or pull
  request number is projection metadata only.
- Visible-text rules for every artifact, requests included: port `checkVisible` and `checkLayout` from maul's
  `internal/report/visible.go`, and add refusal of raw HTML (tags, comments, `<details>`), link and image titles, and
  unused link reference definitions. These are the constructs GitHub's rendered view hides from an approver.
- CLI: `patchy lint intents <dir>` walks the layout, validates every file against its schema, checks `id` uniqueness and
  `depends_on` targets, and with `--base <ref>` refuses a changed `id` or an edited controller-written file. It prints
  `path:line: rule: message` and exits non-zero on any error. `--format json` emits the same findings.
- A reusable workflow `.github/workflows/lint-intents.yml` (`workflow_call`) in patchy that installs a pinned patchy CLI
  release and runs the lint on the caller's pull request.
- The intents repository adopts the contract: requests move to `<project>/<id>/request.md`, `scripts/index.py` and
  `scripts/project_issues.py` follow the new paths, and a pull request workflow calls `lint-intents.yml`.

## How will we know it is done?

- [ ] `go test ./api/artifacts/...` passes golden tests: one valid and several invalid fixtures per artifact kind,
      including a request with an HTML comment, one with a zero-width joiner, and a plan over `PlanMaxRepositories`.
- [ ] A test proves the JSON Schema files and the Go parsers agree on every fixture.
- [ ] Seeded property tests show the parsers never panic and never accept a document with an invisible or bidi
      character.
- [ ] `patchy lint intents testdata/intents` exits 0 on the valid tree and prints one `path:line: rule:` finding per
      seeded defect on the invalid tree, exiting 1.
- [ ] `patchy lint intents --base main` refuses a pull request that changes an existing `id` or edits a
      controller-written `plan-r1.md`.
- [ ] The intents repository's pull request check runs `lint-intents.yml` and passes on its migrated tree.
- [ ] `docs/reference/artifacts.md` in patchy documents every field, bound and rule, generated from the schemas.

## Isolation invariants

- **No credentials in agent pods:** no runtime change. The linter is a workstation and CI tool that reads files only.
  The reusable workflow needs no secret and runs with `contents: read`.
- **Broker-only egress:** no runtime change. The contract gives later intents the plan and request shapes that agent
  pods produce and read, so nothing here widens egress.
- **Custom resources for state, git for artifacts, GitHub as projection:** this intent defines the git half. Approvals
  bind to `{repository, commit, path, sha256}`, intent identity comes from git rather than an issue number, and the
  issue number becomes projection metadata.

## Out of scope

- Writing any artifact from a controller (006 writes records; 016 and 017 write plans and approvals).
- The record envelope for Finding records in 006, beyond registering its kinds as schema `v1` kinds if 006 lands first.
- Agent-side report repair (015).

## Depends on

- None. 006, 011, 015, 016, 017 and 021 depend on this contract.

## References

- `internal/report/plan.go`: `ParsePlan`, its frontmatter and bounds.
- `internal/report/visible.go` and `internal/report/text.go`: visible-text and layout rules.
- `internal/report/build.go`: the build report contract, the basis for the run record body.
- `api/v1alpha1/intent_types.go`: maul's `IntentIssue`, `IntentInput` and `IntentPlan`, whose issue-number identity this
  replaces.
- `docs/design/intent-driven-development.md`, sections "Plan contract and output sanitisation" and "Ending an intent,
  and its name".

## Open questions

- Identity: a frontmatter `id` validated by CI (recommended), or the request pull request or issue number, which keeps
  maul's `IntentName(project, n)` and its 7-digit name budget but ties identity to GitHub?
- Should the plan frontmatter gain `estimated_cost_micro_usd` so plans can be compared with cost budgets from 009?
- Should extension keys (this repository's `phase`, `area`, `refs`, `issue`) be declared in a repository config file, or
  should the schema admit any key with an `x-` prefix?
- Layout: one directory per intent as proposed, or keep this repository's flat `intents/<id>-<slug>.md` for requests and
  put controller-written files elsewhere?
- Should the reusable workflow live in patchy, released with the CLI, or in `bitwise-media-group/github-workflows`?
