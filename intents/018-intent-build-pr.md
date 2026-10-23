---
id: "018"
slug: intent-build-pr
title: "Build an approved plan into a pull request on a create-only branch and archive the outcome"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: high
status: proposed
depends_on:
  - 017-intent-approval
  - 013-repository-image-execution
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_runs.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/run_controller.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/run_settle.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_build.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/github_pr.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/changeset/changeset.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/refs.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/push.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghpush/ghpush.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/intent_pr_body.md.tmpl"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/sanitize.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/intent-controller.yaml"
  - "https://github.com/devthenet-labs/maul/commit/4b3c8a99478b62a02224aae4803c6d5515ce622d"
  - "https://github.com/devthenet-labs/maul/commit/82a345d0b878b3d4a5ff4187b7021630a0688b85"
  - "https://github.com/devthenet-labs/maul/commit/c8d6282c5efae3c248d2763d1b1a798652c0dd8b"
  - "https://github.com/devthenet-labs/maul/commit/8abf38cc59cc8ea83718b2a22aafa75b7b060ef2"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#build-environment-and-changeset-rules"
issue: https://github.com/bitwise-media-group/intents/issues/19
---

# [patchy] Build an approved plan into a pull request on a create-only branch and archive the outcome

## What should change, and why?

After this lands, an approved intent is built and opened as a pull request without a human touching the code. With
`--intent-build` on, intent-controller launches a build Job in the application repository's accepted image. The Job
receives exactly the approved plan bytes and nothing else. The controller validates the changeset, pushes it to a new
`patchy-intent/<intent>` branch that it never force-moves, opens the pull request, follows it to merge or close, and
archives the build record and a final summary to git. This completes the path from an intent file to a merged change.

It keeps maul's strongest guarantees: the build agent receives what the approver approved, the controller never moves a
branch it did not just create, and agent text never carries live references or mentions. The approved bytes now come
from a git blob at the approval commit rather than from a GitHub comment.

Scope:

- Port the build parts of `intent_runs.go` (`runInput`), `run_controller.go` (launch, `stageSpec`, collect, `push`, push
  gate), `run_settle.go`, `intent_build.go` and `github_pr.go` from the pre-rename tree. Leave out network profiles,
  previews, attribution, credential holds and usage rollups.
- Resource classes: add `Project.spec.repositories[].agentResourceClass` (commit `8abf38cc`), resolved against the class
  menu from `013-repository-image-execution`. An unknown class is a Project condition, not a failed run.
- Approval-to-run bridge: at run-input creation, read the plan blob at `status.approval.planRecord.commit`, write an
  immutable `<intent>-build-input-r<N>` ConfigMap, and require the git blob, the ConfigMap and
  `status.approval.planDigest` to agree. Re-hash the ConfigMap at Job launch. A mismatch aborts the run and launches
  nothing.
- The Job mounts the plan as `input/plan.md` and an empty request, per `015-intent-stage-runtime`.
- Image: the build runs only in the repository image pinned and accepted by `013-repository-image-execution`. With none,
  the Intent is `Blocked` with `ImageRequired` and no Job is created.
- Changeset: port `internal/changeset` `IntentRules` (base pin, `--changeset-max-entries`, default 500, and no paths
  under `.github`, `.patchy` or `.devcontainer`). Drop maul's proxy host-string rule, since no egress proxy exists.
- Text: the controller composes the commit message, pull request title and body from `intent_pr_body.md.tmpl`. Agent
  text passes through the `008-command-vocabulary` sanitiser. The body links the plan and approval records (commit and
  path) and names the tracking issue as `Part of <intents repository>#<n>`.
- Push in two phases with `internal/ghpush`: `CreateCommit`, persist the pushed commit on status, then a create-only
  `CreateBranchRef` for `patchy-intent/<intent>`. After a crash, adopt an existing ref only at the persisted commit. A
  foreign ref is `Blocked` with `BranchConflict`. No code path forces a ref or targets the default branch.
- Open the pull request, or adopt only patchy's own same-repository pull request. Keep commit `82a345d0` (contents read
  so private repositories accept it). Poll with `--intent-pr-poll-interval` and move to `Merged` or `Closed`, closing
  the tracking issue.
- Outcomes: `branch_exists`, `image_required`, attempts exhausted leading to `Failed`, `suspend` holding the push, and a
  run whose agent log is gone settled rather than retried forever (commit `c8d6282c`).
- Records: the build run record (`runs/<run>.md` in the 007 layout, holding the fenced build report) and, on a terminal
  phase, `<project>/<id>/summary.md` with pull requests, commits and measured cost, through `006-durable-records`. TTL
  waits until both are archived.
- Narrow intent-controller RBAC in `charts/patchy`. In the agents namespace it gets no `secrets` verbs at all; run
  handoff uses ConfigMaps. In the release namespace it may `get` only the named Forge Secret.

## How will we know it is done?

- [ ] e2e (fake GitHub, fake kubelet): intent file, plan, approval, then a build Job whose `input/plan.md` equals the
      approved plan blob and whose request is empty. A pull request opens from `patchy-intent/<intent>` with a defanged
      body. After a fake merge the Intent is `Merged` and the tracking issue is closed as completed.
- [ ] In that scenario the build run record and `summary.md` are committed, and `patchy records verify intent/<name>`
      passes.
- [ ] Tamper test: changing the build-input ConfigMap after approval aborts the launch with nothing created.
- [ ] A pre-existing `patchy-intent/<intent>` branch at a foreign commit gives `Blocked` with `BranchConflict` before
      any agent runs. A restart between `CreateBranchRef` and the status write adopts the ref at the pushed commit.
- [ ] A changeset that touches `.github/workflows/ci.yml` is refused and nothing is pushed.
- [ ] A unit test proves no code path calls `UpdateRef` with force or names the default branch.
- [ ] A Project repository with no accepted image gives `Blocked` with `ImageRequired` and no Job.
- [ ] A chart render test fails if the intent-controller Role in the agents namespace grants any verb on `secrets`.

## Isolation invariants

- **No credentials in agent pods:** the build pod is brokered and holds no model, forge or cloud credential. The
  changeset leaves the pod as structured data in the envelope. Only intent-controller holds a short-lived token for one
  repository with `contents` and `pull_requests` write, and it cannot read model-key Secrets.
- **Broker-only egress:** the build pod reaches only the broker and the artifact server, under the policy from
  `013-repository-image-execution`. No network profile or dependency route is added; builds that need dependencies wait
  for `023-broker-deps-go` and `024-broker-deps-npm-pypi`.
- **Custom resources for state, git for artifacts, GitHub as projection:** the build input is bound to the approval
  digest and re-verified against git. Build and summary records go to git through the controller. The pull request and
  tracking issue carry controller-composed text that links back to the records.

## Out of scope

- Revise and check-fix rounds (`019-intent-review-rounds`) and multi-repository builds (`020-intent-multi-repo`).
- Previews of intent pull requests (`031-preview-intent-projection`).
- Dependency fetching for builds (`023-broker-deps-go`, `024-broker-deps-npm-pypi`).

## Depends on

- `017-intent-approval`: an approval bound to a plan record commit and digest, and the `BuildDisabled` hold this intent
  releases.
- `013-repository-image-execution`: the pinned, accepted repository image, trusted injection and admission that the
  build Job runs under, and the resource class menu.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/controller/intent/intent_runs.go` (`runInput`), `run_controller.go`
  (`stageSpec`, `push`), `run_settle.go`, `intent_build.go`, `github_pr.go`.
- `internal/changeset/changeset.go` (`IntentRules`), `internal/ghclient/refs.go` (`CreateBranchRef`),
  `internal/ghclient/push.go`, `internal/ghpush/ghpush.go`.
- `internal/templates/intent_pr_body.md.tmpl`, `internal/templates/sanitize.go`.
- `charts/maul/templates/intent-controller.yaml` (the broad agents-namespace Secret rule to narrow).
- Commits `4b3c8a99` (slice 1a), `82a345d0` (private repositories), `c8d6282c` (agent log gone), `8abf38cc` (resource
  classes picked per repository on a Project).
- `docs/design/intent-driven-development.md#build-environment-and-changeset-rules`.

## Open questions

- Should the pull request body link the git records (commit and path) as the primary reference, with the tracking issue
  secondary, so application reviewers can verify what was approved?
- Should an operator be able to allow builds on the default image when no repository image exists, or is `ImageRequired`
  absolute?
- maul's rule that a build is handed no request reasons about GitHub rendering. Is the restated rule (the build sees the
  approved plan only, never the intent file) right for git-rendered markdown?
- How many build attempts before `Failed`, and is revival a new approval or a `/patchy retry`?
- Should the changeset deny list be configurable per Project or per forge, beyond `.github`, `.patchy` and
  `.devcontainer`?
