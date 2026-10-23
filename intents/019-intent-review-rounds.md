---
id: "019"
slug: intent-review-rounds
title: "Revise and check-fix rounds on intent pull requests, fast-forward only and bounded"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: high
status: proposed
depends_on:
  - 018-intent-build-pr
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_revise.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/revise_thread.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_checks.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/check_fingerprint.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/pr_notices.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_blocked.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/working_notes.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/intentperm/intentperm.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/refs.go"
  - "https://github.com/devthenet-labs/maul/commit/925bf579846e670ec536c1c109f24d437f45f35b"
  - "https://github.com/devthenet-labs/maul/commit/4c1a9edbc3576ec2e155b44492fb9248b09e82be"
  - "https://github.com/devthenet-labs/maul/commit/68f40a15b6d03a8826937b6b9f0ae15e896c31c9"
  - "https://github.com/devthenet-labs/maul/commit/82cca98ec5463aed85e33dca2b28699bc58515f9"
  - "https://github.com/devthenet-labs/maul/commit/3a0db3ae1396fdcdd17c6433514da02892d08cfb"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/HANDOFF.md#other-known-follow-ups"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#revise-loop-inputs-and-bounds"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#failed-checks-automatic-fix-rounds"
issue: https://github.com/bitwise-media-group/intents/issues/20
---

# [patchy] Revise and check-fix rounds on intent pull requests, fast-forward only and bounded

## What should change, and why?

After this lands, an approver can ask for changes on an intent pull request and patchy revises it, and a failing named
check is fixed automatically. While an Intent is `InReview`, an approver's `CHANGES_REQUESTED` review, or
`/patchy revise [note]` on the pull request, starts a revise round. A failed check named in `Project.spec.checks.fix`
starts a check-fix round. Each round pushes fast forward only on top of the current head, including commits humans
pushed, and every round is recorded in git. Rounds stop at limits the operator sets, and the Intent waits as `Blocked`
until a human raises them.

Without rounds, every review comment on an agent-built pull request is manual work. With unbounded rounds, spend is
unbounded. maul's design solves both; this intent ports it with round records in git and the per-intent cost ceiling
based on broker-measured spend.

Scope:

- Port `intent_revise.go`, `revise_thread.go`, `intent_checks.go`, `check_fingerprint.go`, `pr_notices.go`,
  `intent_blocked.go` and `working_notes.go` from the pre-rename tree, and the `revise` stage paths in
  `run_controller.go` and `intent_runs.go`. `IntentRun` stage `revise` records its trigger: `review`, `command` or
  `checks`.
- Review trigger: an approver's `CHANGES_REQUESTED` review starts a round after a quiet window of 2 minutes, extended by
  later reviews to at most 10 minutes from the first. Feedback is approver-only, unedited (GraphQL edit history), fenced
  and bounded. Reviews and comments from anyone else never reach a prompt.
- `/patchy revise [note]` and `/patchy retry` on the intent pull request, through `008-command-vocabulary`.
- Check-fix: when a check named in `Project.spec.checks.fix` fails on patchy's own head, start a round with the
  annotations and log tail fenced as data. With `checks.rerunFailed`, re-run the failed Actions jobs once first, and do
  not count a round if the re-run passes.
- Fix the repeat-failure fingerprint as maul's HANDOFF asks: hash the annotations and a timestamp-stripped log tail, so
  a repeated Actions failure is detected and blocks instead of looping.
- Round input: pin the pull request head, then hand the agent the approved plan (re-hashed against
  `status.approval.planDigest` and placed first), the bounded thread, the previous round's working notes, the last
  failure and the compare patch. Read working notes from the archived record of the previous round, not from `IntentRun`
  status.
- Push with `FastForwardRef` only. If the head moved during the round (`head_moved`), re-pin and re-run once. On a
  second move, post a notice and wait. Never force.
- Limits: `Project.spec.limits.maxRevisions`, `maxCheckFixes` and `maxCostMicroUSD`. The cost ceiling uses the
  broker-measured cost from `009-broker-spend-limits`, never CLI-reported usage. Breaking a limit gives `Blocked` with a
  reason naming it, and raising the limit resumes the Intent in the phase it was blocked from.
- Add the check-fix grants to `internal/intentperm` (`checks`, `statuses` and `actions` read; `actions` write only with
  `rerunFailed`) and prove each before the Project is `Ready`.
- Records: one run record per round (`runs/<run>.md` in the 007 layout) through `006-durable-records`, with round
  number, trigger, approver, input digest, outcome, pushed commit and measured cost. Round notices on the pull request
  are one-way projections. TTL waits for both.

## How will we know it is done?

- [ ] e2e: `CHANGES_REQUESTED` from an approver starts a revise Job whose input begins with the exact approved plan
      bytes. It pushes fast forward, posts one round notice, returns to `InReview`, and the round's run record is
      committed with `trigger: review`.
- [ ] e2e: a human commit pushed during a round gives `head_moved` and one re-run. A second move gives a notice and a
      wait, and no ref is forced.
- [ ] e2e: a failing check named in `checks.fix` starts a check-fix round. With `rerunFailed`, a re-run that passes
      starts no round and leaves `status.checkFixes` unchanged.
- [ ] A unit test feeds two Actions logs that differ only in timestamps and runner metadata and gets the same
      fingerprint. The repeat blocks the Intent.
- [ ] With `maxRevisions: 1`, a second review round gives `Blocked` and launches no Job. Raising the limit to 2 resumes
      `InReview` and the round runs.
- [ ] A round that would push the Intent past `maxCostMicroUSD`, using broker-measured cost, gives `Blocked`.
- [ ] A review from a non-approver, or an edited approver comment, never starts a round and never appears in a round
      input fixture.
- [ ] A Project with `checks.fix` set but no `checks` read grant is not `Ready`, and its condition names the grant.

## Isolation invariants

- **No credentials in agent pods:** revise and check-fix pods are build pods: brokered, in the same accepted repository
  image, with no credential. Pushes, reruns and notices are done by intent-controller with per-operation,
  single-repository tokens.
- **Broker-only egress:** round pods reach only the broker and the artifact server. maul's network profiles are not
  ported. Dependency access arrives only through `023-broker-deps-go` and `024-broker-deps-npm-pypi`.
- **Custom resources for state, git for artifacts, GitHub as projection:** round counters, limits and checks observed
  live on `Intent` status. Each round's input digest, outcome and pushed commit are git records. GitHub reviews,
  comments and checks are read as authority and CI facts only.

## Out of scope

- Check-fix rounds for Finding pull requests.
- Multi-repository rounds (`020-intent-multi-repo`) and previews of pull request heads.
- Network profiles and any dependency egress.

## Depends on

- `018-intent-build-pr`: the intent pull request, `patchy-intent/<intent>` branch, accepted image, build record and the
  `InReview` phase that rounds start from. Through its chain, `009-broker-spend-limits` for measured cost.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/controller/intent/intent_revise.go`, `revise_thread.go`,
  `intent_checks.go`, `check_fingerprint.go`, `pr_notices.go`, `intent_blocked.go`, `working_notes.go`.
- `internal/intentperm/intentperm.go` (check-fix grants), `internal/ghclient/refs.go` (`FastForwardRef`).
- Commits `925bf579` (bounded rounds), `4c1a9edb` (GraphQL edit history for feedback), `68f40a15` (scoped feedback and
  persisted notices), `82cca98e` (re-run failed Actions checks once), `3a0db3ae` (working notes).
- `HANDOFF.md#other-known-follow-ups` (the check-fix fingerprint that never matches).
- `docs/design/intent-driven-development.md#revise-loop-inputs-and-bounds` and `#failed-checks-automatic-fix-rounds`.

## Open questions

- `009-broker-spend-limits` is only a transitive dependency. Should it be listed directly, since the cost ceiling cannot
  work without broker-measured usage on every round?
- Should `/patchy revise` be accepted from any user with write permission, or only from `Project.spec.approvers`?
- Should a round blocked by a limit be resumed by raising the limit only, or also by an explicit `/patchy retry`?
- Should the round record include the compare patch, or only its digest with the patch in the blob mirror? The 007
  run-record shape has no field for round trigger or approver yet.
- Is a 6 KiB cap on working notes still right when they are read from git rather than from status?
