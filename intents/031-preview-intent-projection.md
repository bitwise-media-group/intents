---
id: "031"
slug: preview-intent-projection
title: "Deploy a preview for every open intent pull request and record it in git"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 6
area: previews
effort: medium
status: proposed
depends_on:
  - "028-preview-slots"
  - "030-preview-image-supply"
  - "018-intent-build-pr"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/preview.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/preview_view.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/preview_comments.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/intent_preview.md.tmpl"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/preview_components.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#previews-one-host-one-component-per-repository"
  - "https://github.com/devthenet-labs/maul/commit/5d2cb1ef7c7a89a22b1d7aa73d48567cdd1c05fd"
  - "https://github.com/devthenet-labs/maul/commit/76e6ac9cb177d3d8bd0c75b59075951b3ed2295e"
issue: https://github.com/bitwise-media-group/intents/issues/32
---

# [patchy] Deploy a preview for every open intent pull request and record it in git

## What should change, and why?

When an intent has an open pull request in a repository its Project marks for previews, patchy creates the intent's
Preview without anyone writing YAML. The Preview runs the recorded pull request head in each changed repository and the
recorded default-branch commit in each unchanged one, all on one host at one path per repository. A reviewer finds a
markdown record of each preview event (live, changed, failed, expired, removed) in the Project's records repository, and
the same text as a sticky comment on each pull request. Deleting that comment loses nothing.

maul writes Preview specs from the Intent too, but keys the host label on the GitHub issue number (`<project>-<issue>`)
and keeps the only human-facing record in GitHub comments, whose ids sit on Intent status. Under the working assumptions
the Intent CR is the state, git holds the record, and GitHub is a projection. maul also relies on convention alone to
keep its deliberately vulnerable target repository from being previewed. This intent makes that a Project setting.

Scope:

- Project CRD: add `repositories[].preview` (`imageRepository` leaf, `port`, `readinessPath`, `path`) and the
  one-repository shorthand `spec.preview`, with maul's CEL rules: at most four previewed repositories, unique paths, and
  no shorthand beside per-repository config. Add `repositories[].previewForbidden`. CEL refuses `preview` beside it, and
  every derivation step re-checks it.
- `PreviewSourceReconciler` in intent-controller, ported from maul's `internal/controller/intent/preview.go`. It is the
  only writer of Preview spec, apart from the digest field owned by 030. It builds the spec through the shared pure
  `DesiredPreviewComponents(project, intent)` and writes `revision` only, so 030 resolves each digest.
- Revisions come only from what is recorded on the Intent CR: pull request heads recorded by 018 (and 020 for
  multi-repository intents) and `status.previewBases[]`. Take each base from the source-controller Repository snapshot
  of the default branch, recorded once on the first review pass and never rewritten. Do not read heads back from GitHub
  issues or comments.
- Lifecycle: create a Preview only in `InReview` or `Revising` (or `Blocked` from either) while at least one intent pull
  request is open. Delete it when the last one merges or closes, or when the intent ends.
- preview-controller gains maul's re-check for Previews that carry `intentRef`: re-derive the components from the Intent
  and Project and refuse a mismatch with condition `SpecMismatch`.
- Host label: the canonical Intent CR name `<project>-<id>` (007, 016), not an issue number. Labels longer than 63
  characters are cut and given an 8-character hash suffix. The label is set once and is immutable. Renaming the intent
  file does not change it. A label already in use by another Preview UID is refused with a condition, never reused.
- Records: on each transition, render the event from a ported `intent_preview.md.tmpl` (components, revisions, digests
  from 030, URL, phase, timestamps) and hand it to the 006 writer at `<project>/<id>/previews/<seq>-<event>.md`, beside
  the intent's other records in the 007 layout. 007 has no preview kind yet, so this intent registers one. Never include
  `status.message`.
- Projection: one sticky comment per previewed pull request and a preview line in the intent's issue status comment,
  posted best effort under the existing rate floor. The text is the record's own bytes plus a link to the record. Record
  the comment id and digest on Intent status only to edit in place.

## How will we know it is done?

- [ ] envtest: an Intent in `InReview` with one open pull request and a previewed repository yields a Preview whose spec
      equals `DesiredPreviewComponents`; closing the pull request deletes it.
- [ ] envtest, multi-repository: an unchanged repository uses the recorded base, and a later default-branch push does
      not rewrite `status.previewBases`.
- [ ] envtest: a Project with `previewForbidden: true` beside `preview` is refused by CEL, and an Intent in that
      repository never gets a Preview. A hand-applied Preview naming that Intent is refused by preview-controller.
- [ ] envtest: an Intent created from a git intent file with no GitHub issue gets a valid, stable host label, and
      renaming the file keeps the label.
- [ ] e2e with the 005 fake kubelet, the 006 fake records target and `e2e/fakegithub`: when the Preview turns Ready, a
      record appears in the records repository, and the pull request comment body equals the record's bytes plus the
      link line.
- [ ] e2e: deleting the pull request comment and forcing a resync recreates it from the record and the CR. Nothing is
      read back from GitHub.
- [ ] e2e: expiry and removal each produce their own record, and the comment is edited, not duplicated.

## Isolation invariants

- **No credentials in agent pods:** no change to agent or slot pods. The reconciler reads only operator Project config
  and heads recorded by controllers, never issue text or agent output. Records and comments are written controller-side
  with the existing scoped forge token and records credential.
- **Broker-only egress:** unchanged. Slots still have no egress. A preview that needs staging services is not supported
  here (see open questions).
- **Custom resources for state, git for artifacts, GitHub as projection:** the Intent and Preview CRs hold state, each
  preview event is a git record, and GitHub comments are rendered from the record and never parsed back. Comment ids on
  Intent status are only edit handles.

## Out of scope

- The plan and build flows and how pull request heads are recorded (016 to 020).
- Outbound access from slots, including broker-mediated calls to staging dependencies.
- Showing previews on the status page (a follow-up to 025).
- Editing pull request bodies, which a squash merge can copy onto the default branch.

## Depends on

- `028-preview-slots`: the Preview CRD, slots and preview-controller that render the spec this intent writes.
- `030-preview-image-supply`: revision-only components resolved to digests, and digests to put in records.
- `018-intent-build-pr`: Intents in review with recorded pull request heads, the phase 3 Project CRD, and the records
  path for intent artifacts. Multi-repository heads come from 020, which lands earlier in phase 3.

## References

- `internal/controller/intent/preview.go` (`desiredPreview`, `recordPreviewBases`), `preview_view.go` and
  `preview_comments.go` at `devthenet-labs/maul@55b163a8`.
- `internal/templates/intent_preview.md.tmpl`, `internal/templates/intent_preview.go` and the fixtures
  `internal/templates/testdata/intent_preview_*.md`.
- `api/v1alpha1/preview_components.go` and `api/v1alpha1/project_types.go` (`ProjectRepositoryPreview`).
- `docs/design/intent-driven-development.md` sections "Previews: one host, one component per repository" and "Naming and
  the preview image prefix"; line 41 notes the deliberately vulnerable target must never be previewed.
- Commits 5d2cb1ef (preview link on issue and pull requests), 7c7fc36c (queued preview message), 76e6ac9c
  (multi-repository fields and multi-component previews).

## Open questions

- Should `020-intent-multi-repo` be a declared dependency, given that multi-repository previews need its recorded heads?
- Intent names `<project>-<id>` are unique, but two can collide once cut to 63 characters with a hash suffix. Is
  refusing the second one with a condition, as proposed, acceptable?
- Should previews ever get outbound access to staging APIs? maul ships none. If yes, it must go through the egress
  broker with broker-held credentials and an audience-bound slot identity, never through egress-proxy or mounted
  Secrets, and it needs its own intent.
- Does every preview event deserve its own git commit, or should changes within a short window be batched to keep
  records history readable?
