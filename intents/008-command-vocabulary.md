---
id: "008"
slug: command-vocabulary
title: "One /patchy command grammar with write-permission authority and a single agent-text sanitiser"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 1
area: intents
effort: medium
status: proposed
depends_on:
  - 005-e2e-agent-pods
refs:
  - "https://github.com/devthenet-labs/maul/commit/798a9618369710e4131bfa830919ea1df7ad1b08"
  - "https://github.com/devthenet-labs/maul/commit/f8bb8b1ceac411891474ff53639ddbf62ba855fc"
  - "https://github.com/devthenet-labs/maul/commit/442d9dc34b13f83d1627f8fbc243d3fc7da61b00"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/command"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/integration/commands.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/sanitize.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/finding_text.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#human-commands-one-vocabulary"
issue: https://github.com/bitwise-media-group/intents/issues/9
---

# [patchy] One /patchy command grammar with write-permission authority and a single agent-text sanitiser

## What should change, and why?

A maintainer with write access to a Finding's repository can comment `/patchy approve`, `/patchy retry`,
`/patchy suspend`, `/patchy resume` or `/patchy expedite` on its tracking issue. The integration-controller applies the
command through `action.Apply`, the same function the status page and `patchy` CLI use, and answers with exactly one
reply. Anyone else gets one refusal and then silence. Separately, every piece of agent-authored text that patchy posts
to GitHub passes through one sanitiser, so an agent's `Fixes #12 @octocat` can never close a tracking issue or ping
anyone.

Today `internal/controller/integration/webhooks.go` accepts `/approve` (or the Integration's
`spec.github.issues.approveComment`) from any commenter whose `author_association` is in an allowlist. That admits
organisation members without write access to the repository, and it is the only command. Agent text reaches PR titles,
bodies, commit messages and comments with live closing keywords and mentions. maul fixed both (#41, #48, #50), and the
intent flow (016 to 019) builds its human authority on the same grammar and rule. Commands stay aliases that write the
Finding custom resource; nothing is parsed back from GitHub as state.

Scope:

- Port `internal/command` (parser, surfaces, property tests) from `devthenet-labs/maul@86a3f567^` with the `/patchy`
  prefix. A command is a whole line at the start of a comment, never quoted, indented or fenced.
- Authority rule, in one function: the commenter has `write`, `maintain` or `admin` from the collaborator-permission
  API, is not a bot (`user.type` is not `Bot`), and the comment was never edited (checked with GraphQL `lastEditedAt` at
  settle time). `author_association` is no longer consulted.
- Finding `status.commands` (`pending`, `consumed`, `lastToggle`) with maul's bounds (8 pending, 32 consumed, 2
  undecided per account). The webhook records the command and acks; a settle loop applies it with backoff, so a
  redelivered webhook never applies a command twice.
- An applied command records the commenter's numeric GitHub id beside the login (`spec.approval.byID`, and the same
  field on retry and expedite), because a login can be renamed. 021 attributes runs by this id.
- One eyes reaction on receipt and exactly one reply per command. Refusals are bounded per account, then quiet.
- `/approve` and a custom `approveComment` stay accepted as deprecated aliases for one minor release, with a reply that
  names the new command. The Integration field is marked deprecated in the CRD.
- Port `internal/templates/sanitize.go` and `finding_text.go`, plus the `internal/report` text helpers they share. Apply
  the sanitiser to the remediation PR title, body and commit message and to every report comment: HTML escaped,
  `@mentions` and `#refs` neutralised outside code, closing keywords (`fixes`, `closes`, `resolves` and their forms)
  defanged, and plain-text defanging for commit messages.
- Docs: `docs/labels.md` gains the command table, and `docs/status-ui.md` notes the deprecated `/approve`.

## How will we know it is done?

- [ ] Ported `e2e/commands_test.go` on the 005 harness passes: each of the five verbs from a write-access user is
      applied to the Finding spec exactly as `patchy approve finding <name>` would apply it.
- [ ] The same e2e shows a read-only commenter gets one refusal, then no reply to a second attempt; a bot account gets
      none; an edited command is refused; a redelivered webhook does not apply a command twice.
- [ ] e2e: an organisation member without write access who comments `/approve` is refused, which is the documented
      behaviour change.
- [ ] `go test ./internal/command ./internal/templates` passes seeded property tests: the parser never panics, a quoted,
      indented or fenced command never parses, and sanitiser output holds no raw HTML and no live mention, reference or
      closing keyword outside code.
- [ ] A golden test renders a remediation PR whose agent text is `Fixes #12 @octocat <img src=x>`; the title, body and
      commit message are defanged.
- [ ] The existing Finding pipeline e2e passes unchanged apart from the `/approve` tightening.

## Isolation invariants

- **No credentials in agent pods:** no agent pod changes. Parsing, the permission check and settling run in
  integration-controller with its existing, controller-side GitHub App tokens.
- **Broker-only egress:** unchanged. The only new GitHub calls (collaborator permission, GraphQL edit check) come from
  integration-controller.
- **Custom resources for state, git for artifacts, GitHub as projection:** a command is recorded on Finding status and
  applied as a write to the Finding spec. The tracking issue remains a one-way projection with human signals flowing
  back after an authority check.

## Out of scope

- Intent verbs (`plan`, `replan`, `cancel`, `revise`) and plan-PR commands; 016 to 019 add them on this grammar.
- New status page or CLI actions beyond the existing `action.ActionVerbs`.
- Approver allowlists; Findings keep relying on repository write permission alone.

## Depends on

- `005-e2e-agent-pods`: the fake-kubelet harness and the fakegithub additions (GraphQL `lastEditedAt`, collaborator
  permission, reactions) the command e2e needs.

## References

- `commit 798a9618` feat(command): the shared, pure GitHub command parser (#41).
- `commit f8bb8b1c` feat(integration)!: Finding commands use the shared grammar and a write-permission check (#48).
- `commit 442d9dc3` fix(integration): quiet only commenters who fail the write-access check (#50).
- `internal/command`, `internal/controller/integration/commands.go`, `api/v1alpha1/finding_types.go` (`FindingCommands`
  and its bounds), `internal/ghclient/collaborators.go`.
- `internal/templates/sanitize.go` and `internal/templates/finding_text.go`.
- `docs/design/intent-driven-development.md`, section "Human commands: one vocabulary".

## Open questions

- How long do `/approve` and `spec.github.issues.approveComment` stay as aliases: one minor release, or until the
  rebrand in 033?
- Should `triage` permission count for `suspend` and `resume`, which change no code, while `approve` needs `write`?
- Should refusals be silent from the first attempt for accounts with no repository access at all, to avoid giving
  drive-by commenters a reply channel?
- Does the sanitiser also apply to investigation reports posted on the tracking issue, which are long and often quote
  code with `#` and `@`?
