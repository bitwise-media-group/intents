---
id: "017"
slug: intent-approval
title: "Approve a plan by binding to its commit and digest, from a plan PR, the CLI or a command"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: medium
status: proposed
depends_on:
  - 016-intent-planning
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_actions.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/review.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/graphql.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/action/action.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/admission-policy.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/intent_types.go"
  - "https://github.com/devthenet-labs/maul/commit/e2f94dd72eac66d66e53d649ce3c435485994d00"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#human-commands-one-vocabulary"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-github-permissions.md"
issue: https://github.com/bitwise-media-group/intents/issues/18
---

# [patchy] Approve a plan by binding to its commit and digest, from a plan PR, the CLI or a command

## What should change, and why?

After this lands, an approver can approve an intent's plan in one of three ways, and every one of them produces the same
auditable approval. The approval names the exact bytes approved:
`{intents repository, commit SHA, plan path, blob SHA, sha256}` plus the request digest it was planned from. It is
recorded on the `Intent` and written to git as an approval record, so it survives the deletion of the custom resource at
TTL.

maul binds approval to a GitHub plan comment, re-fetched and checked for edits, and to the live issue body still
rendering to the snapshot digest. That depends on GitHub comment immutability and is lost once the issue is the only
copy. Here the approval binds to a git commit, which is immutable, and GitHub supplies only authority facts: who
reviewed which commit, and whether they have write permission.

Scope:

- Plan pull request (the primary surface, `Project.spec.approval.pullRequest`, default `true`). With it on, the plan
  record commit Y that `016-intent-planning` stores in `status.plan.record` is written on a create-only branch
  `patchy-plan/<intent>-r<N>` instead of the records branch, using the `006-durable-records` git primitives
  (`CreateCommit`, `CreateBranchRef`). intent-controller opens a pull request authored by the App. The body names Y, the
  plan path, the plan sha256 and the pinned request, and shows the plan verbatim in a code fence. Replan closes the old
  pull request.
- Accept an `APPROVED` review only if: `review.commit_id` is Y, the branch head is still Y, Y is the commit the
  controller recorded, the tree diff from Y's parent holds only the plan record, the plan blob hashes to
  `status.plan.digest`, the request at the pinned commit still hashes to `status.input.sha256`, and the reviewer is
  authorised. A `CHANGES_REQUESTED` review is a replan request.
- CLI: `patchy approve intent <name> --plan <sha12>` writes `spec.approval` as a JSON merge patch (as commit `e2f94dd7`
  does for Findings). Add the `approve` verb on `intents` to `internal/action`, the RBAC custom verb, and a rule in
  `charts/patchy/templates/admission-policy.yaml`: the caller needs `approve` on `intents`, the named digest prefix must
  match `status.plan.digest`, and `by` must equal the requesting user.
- Commands: `/patchy approve <sha12>` on the tracking issue or the plan pull request, through `008-command-vocabulary`,
  writes the same `spec.approval`. The approve label is an alias that binds to the plan revision current at the label
  event. Both need the approvers allowlist, write permission, not a bot, and an unedited comment (GraphQL
  `lastEditedAt`).
- `status.approval` records
  `{by, byID, subject, source, eventID, at, planRevision, planDigest, requestCommit, requestDigest}` and
  `planRecord {repository, commit, path, blobSHA}`. `source` uses the 007 approval values: `review`, `cli` or `command`
  (a label is recorded as `command`); `026-intent-actions` adds `status-page`.
- Refusal: an approval for a stale digest, before the plan record exists, after the request or plan changed, or from an
  unauthorised actor gets one notice, an `ApprovalRefused` condition and the label removed. A changed request marks the
  plan stale and asks for a replan.
- Re-check the plan against the 007 visible-text rules at approval time. A plan holding raw HTML or a hidden markdown
  construct is refused, because a rendered view could differ from the bytes the build receives.
- Write `<project>/<id>/approval-r<N>.md` through `006-durable-records`. On a plan pull request approval, merge it with
  a merge commit so Y stays reachable from the default branch.
- Without `018-intent-build-pr` the approved Intent moves to `Building` and holds there with `BuildDisabled`.

## How will we know it is done?

- [ ] e2e: an `APPROVED` review at commit Y on the plan pull request moves the Intent to `Building` with
      `BuildDisabled`. `status.approval.planRecord.commit` is Y, `planDigest` matches, and Y is reachable from the
      default branch after the merge.
- [ ] `approval-r1.md` exists in the records location and `patchy records verify intent/<name>` (from
      `006-durable-records`) confirms it binds the plan sha256 and the request digest.
- [ ] envtest: a user with `update` on intents but without the `approve` custom verb is refused by admission. A user
      with it succeeds, and a stale `--plan` prefix is refused.
- [ ] e2e: `/patchy approve <sha12>` from an approver yields the same `status.approval` apart from `source`. A wrong
      prefix gets one refusal reply.
- [ ] A refusal table test covers: a review at an older commit, a branch head moved by a human push, a commit not
      created by the controller, a request changed after planning, a non-approver, a bot, an edited comment and an
      approval before the plan record. Each gets one notice and nothing is recorded as approved.
- [ ] Editing the tracking issue body after approval does not revoke it.
- [ ] After TTL deletes the Intent, the approval record and plan record still verify from git alone.

## Isolation invariants

- **No credentials in agent pods:** no agent runs in this intent. Plan branches, pull requests, merges and records are
  written by intent-controller with per-operation tokens for the intents repository only (`contents` and `pull_requests`
  write).
- **Broker-only egress:** unchanged. Approval adds no pod and no egress path.
- **Custom resources for state, git for artifacts, GitHub as projection:** the approval is state on the `Intent` and a
  record in git, and it binds to a git commit and sha256. GitHub reviews, comments and labels are authority signals that
  write the custom resource after a check. They are never the content that is approved.

## Out of scope

- Launching builds (`018-intent-build-pr`).
- The other intent actions and the status page (`026-intent-actions`).
- Multi-approver quorum and separation-of-duty policies.

## Depends on

- `016-intent-planning`: the `Intent` CRD, the pinned request, the plan record at a recorded commit and the tracking
  issue. Through it, the records writer from `006-durable-records` and the command grammar from
  `008-command-vocabulary`.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/controller/intent/intent_actions.go` (`settlePlanApproval`,
  `approvalChanged`, `refuseApproval`).
- `internal/ghclient/review.go` (review commit SHA), `internal/ghclient/graphql.go` (edit history).
- `api/v1alpha1/intent_types.go` (`IntentApproval`, `IntentAction`).
- `internal/action/action.go` (intent verbs declared but not wired), `charts/maul/templates/admission-policy.yaml`.
- Commit `e2f94dd7` (spec actions written as merge patches).
- `docs/design/intent-driven-development.md#human-commands-one-vocabulary`, `docs/design/intent-github-permissions.md`.

## Open questions

- Is the plan pull request with an `APPROVED` review the right primary surface, with the CLI and `/patchy approve` as
  aliases? Or should issue-centric approval stay primary?
- Approvers: GitHub logins, Kubernetes subjects, or both? Must a CLI approver also appear in `Project.spec.approvers`,
  or is the RBAC custom verb enough?
- Should the label alias be kept at all, since a label cannot name a digest?
- Should the controller merge the plan pull request on approval (needs merge commits allowed and a ruleset bypass), or
  leave merging to humans and accept that Y lives on a branch until then?
- Should every approval need the plan pull request, or may an operator turn it off for repositories where only the CLI
  is used?
