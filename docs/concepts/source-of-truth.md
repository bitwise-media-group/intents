---
description:
  "Custom resources hold state, git and blob storage hold artifacts, and GitHub issues are a one-way projection."
---

# Git as the source of truth

patchy already separates state from presentation. A `Finding` custom resource carries the pipeline's state, and its
GitHub tracking issue is rendered from it, never parsed back. This work extends the same split to everything a PDLC
produces, and adds a third leg: durable hard copies in git.

| Where            | Holds                                                            | Lifetime                           |
| ---------------- | ---------------------------------------------------------------- | ---------------------------------- |
| Custom resources | The state machine: phases, runs, approvals, limits, receipts     | Until the TTL after an intent ends |
| Git and blob     | The artifacts: requests, plans, approvals, run and usage records | Permanent, immutable once written  |
| GitHub issues    | A projection for discussion, assignment and boards               | Whatever GitHub keeps              |

## Why maul's model has to change

maul treats the GitHub issue body as the authoritative request. It snapshots the body, hashes it, and binds the approval
to that digest and to the plan comment it posted. Approval integrity therefore depends on GitHub comment immutability,
re-fetched and checked against edit history. The input snapshot and the plan live in ConfigMaps owned by the `Intent`,
and are deleted with it 14 days after it ends. After that, the only record of what was asked, what was planned and who
approved it is the issue and its comments.

## The model here

- **Requests are files.** An intent is a markdown file in an intents repository, like the files on this site. It becomes
  authoritative when it is merged. Its request is pinned as `{repository, commit, path, sha256}`
  ([016](../intents/016-intent-planning.md)).
- **Plans are records.** The planner's report is written by the controller as an immutable plan record in git, then
  projected onto the issue verbatim, in a code block ([016](../intents/016-intent-planning.md)).
- **Approval binds bytes.** An approval names the intents repository, the commit SHA of the plan record, the plan path,
  its blob SHA and its sha256, plus the request digest it was planned from. The primary surface is an `APPROVED` review
  on a plan pull request at that exact commit. `patchy approve intent` and `/patchy approve <sha12>` are aliases that
  write the same approval to the custom resource ([017](../intents/017-intent-approval.md)).
- **Everything else is a record too.** Build, revision and check-fix outcomes, preview lifecycles, image provenance and
  monthly usage are written through one controller-side records writer, with a content-addressed blob mirror for
  transcripts and other large or sensitive artifacts ([006](../intents/006-durable-records.md)).
- **TTL waits for archival.** An ended `Intent` is deleted only after its records are confirmed written, so nothing is
  lost when the custom resource goes.
- **GitHub stays useful.** Labels and `/patchy` commands remain accepted, as aliases that write the custom resource
  after an authority check: an approvers allowlist, write permission, not a bot, and an unedited comment
  ([008](../intents/008-command-vocabulary.md)). They are never the content that is approved.

## One contract for every artifact

Requests, plans, approvals and run records follow versioned schemas with a validator, `patchy lint intents`, and a
reusable CI check for intents repositories ([007](../intents/007-artifact-contract.md)). The
[authoring skills](../areas/skills.md) write to the same contract. This repository already follows an early form of it:
`make lint` validates every intent file.

## Records repositories are private by default

Plans and reports in git history are permanent, unlike an editable comment. A records repository is private unless an
operator explicitly allows a public one, and the records use the same public-wording renderers as the dashboard. This
repository is public because it holds specifications, not records of real runs.
