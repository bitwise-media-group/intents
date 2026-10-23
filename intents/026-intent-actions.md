---
id: "026"
slug: intent-actions
title: "Approve, replan, cancel, revise, suspend and retry intents from the status page and CLI"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 5
area: ux
effort: high
status: proposed
depends_on:
  - 025-intents-dashboard
  - 017-intent-approval
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/action/action.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/action/policy_envtest_test.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/command/command.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/action.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/cani.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/admission-policy.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/intents.go"
  - "https://github.com/devthenet-labs/maul/commit/e2f94dd72eac66d66e53d649ce3c435485994d00"
  - "https://github.com/devthenet-labs/maul/commit/f8bb8b1ceac411891474ff53639ddbf62ba855fc"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#human-commands-one-vocabulary"
issue: https://github.com/bitwise-media-group/intents/issues/27
---

# [patchy] Approve, replan, cancel, revise, suspend and retry intents from the status page and CLI

## What should change, and why?

After this lands, a permitted user can act on an intent without going to GitHub. From the intent detail on the status
page, or with `patchy <verb> intent <name>`, they can approve the current plan, ask for a replan, cancel, start a revise
round with a note, retry a failed intent, and suspend or resume one. Each action is a JSON merge patch on the `Intent`
spec, allowed by an RBAC custom verb and checked by the ValidatingAdmissionPolicy, exactly as Finding actions are today.
GitHub labels and `/patchy` comments remain aliases that write the same spec fields after an authority check, so the
custom resource is the single place an action takes effect.

maul has no non-GitHub write path for intents: its action registry declares the intent verbs but nothing wires them.
patchy's Finding actions (`internal/action`, the admission policy, `POST /api/findings/{name}/actions/{verb}` and
`patchy approve`) are already the right pattern. `017-intent-approval` adds the `approve` verb for intents and the CLI
command. This intent adds the rest, puts all intent verbs behind one registry, and brings them to the status page.

Scope:

- `internal/action`: register the intent verbs `replan`, `cancel`, `revise`, `retry`, `suspend` and `resume` for kind
  `Intent`, beside the `approve` verb that 017 registers. Each writes one spec field (`spec.replan`, `spec.cancel`,
  `spec.revise`, `spec.retry`, `spec.suspend`) carrying `by`, `at`, an optional `note`, and, where it acts on a plan,
  `planRevision`, `planDigest` and the plan record commit. Apply the same semantics as the `internal/command` verbs. An
  approval from the status page writes 017's `spec.approval` with the 007 approval source `status-page`.
- intent-controller consumes each field once, records the outcome on status, and posts one projection notice to the
  tracking issue or the intent pull request. An action that is not valid in the current phase is refused with a
  condition, never queued.
- Admission: add custom verbs on `intents` for the new verbs to `charts/patchy/templates/admission-policy.yaml`, next to
  017's `approve` rule, with field guards: only the field matching the granted verb may change, `by` must equal the
  requesting user, `replan` must name the current `status.plan.digest`, and `revise` is refused outside `InReview`.
- Refuse any action that would launch a run on a harness that is not brokered. The status page does not offer it, the
  CLI explains why, and the controller refuses it as a last line.
- status-server: `POST /api/intents/{name}/actions/{verb}` behind the existing hardened action envelope (session, CSRF,
  access review per verb), and an action bar in the intent detail from `025-intents-dashboard`. Each button shows the
  plan digest and record commit it acts on.
- CLI: generalise `cmd/patchy/internal/cli/action.go`, which already has 017's `patchy approve intent`, to
  `patchy replan|cancel|revise|retry|suspend|resume intent <name>`, with `--plan <sha12>` where it applies and `--note`
  for `revise` and `replan`. Write merge patches for Findings and Intents, as maul's commit `e2f94dd7` does, so Helm
  keeps its fields. Extend `patchy can-i` to the intent verbs.
- GitHub aliases are not registered here. The commands that 016 (`plan`, `replan`, `cancel`), 017 (`approve` and the
  approve label) and 019 (`revise`, `retry`) add through the `008-command-vocabulary` grammar are changed, where needed,
  to write the same spec field as the matching action verb, so every surface takes effect in one place.
- Docs: an action matrix (verb, phases, RBAC verb, GitHub alias) and intent rules in the users RBAC example.

## How will we know it is done?

- [ ] envtest: for each intent verb, a user with `update` on intents but without the custom verb is refused by
      admission, and a user with it succeeds. A patch that changes a field other than the granted verb's is refused.
- [ ] envtest: `approve` or `replan` naming a stale plan digest is refused, and `by` set to another user is refused.
- [ ] e2e: a plan finishes, `patchy approve intent demo-001 --plan <sha12>` is applied, and a build Job launches. The
      approval records the plan record commit, and the tracking issue gets exactly one notice.
- [ ] e2e: the same approval through `POST /api/intents/demo-001/actions/approve` and through a `/patchy approve`
      comment produces an identical spec write apart from the source.
- [ ] e2e: `patchy suspend intent` holds a running intent before its next launch or push, and `resume` releases it.
      `patchy cancel intent` ends it as `Closed`.
- [ ] `patchy can-i approve intents -n patchy` reports correctly for a user with and without the verb.
- [ ] After a CLI action, `helm upgrade` of `patchy-config` reports no server-side apply conflict.
- [ ] The status page offers no action for an Intent on a Project whose harness is not brokered, and the CLI refuses
      with a message naming the harness.

## Isolation invariants

- **No credentials in agent pods:** actions write only Kubernetes custom resources through RBAC and admission. No
  credential is added anywhere, and actions that would start a run on a non-brokered harness are refused.
- **Broker-only egress:** unchanged. status-server and the CLI talk only to the Kubernetes API; status-server holds no
  forge token for actions.
- **Custom resources for state, git for artifacts, GitHub as projection:** the action takes effect on the `Intent` spec
  and is bound to the plan digest and its record commit. GitHub comments and labels are aliases that write the same
  field after an authority check, and notices back to GitHub are one-way.

## Out of scope

- The `approve` verb, its admission rule and `patchy approve intent` (`017-intent-approval`). This intent adds only the
  status-page approve button.
- Registering `/patchy` commands for intents (016, 017 and 019).
- Bulk actions over intents beyond a label selector (`-l`).
- Multi-approver quorum and separation-of-duty policies.
- Editing intents or creating them from the status page; intake stays in git (`016-intent-planning`).

## Depends on

- `025-intents-dashboard`: the intent detail view and the status-server routes the action bar joins.
- `017-intent-approval`: the `approve` verb on intents, `spec.approval`, the digest-bound approval checks and the GitHub
  alias authority rule that the other verbs reuse.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/action/action.go` (intent verbs declared, not wired),
  `internal/action/policy_envtest_test.go`, `internal/command/command.go`.
- `cmd/maul/internal/cli/action.go` (merge patch write), `cmd/maul/internal/cli/cani.go`.
- `charts/maul/templates/admission-policy.yaml`, `internal/web/intents.go` (read-only intent routes).
- Commits `e2f94dd7` (spec actions as merge patches), `f8bb8b1c` (shared grammar and write-permission check).
- `docs/design/intent-driven-development.md#human-commands-one-vocabulary` (slice 5 intent actions).

## Open questions

- Should approvers be Kubernetes subjects only for these actions, or must the user also appear in
  `Project.spec.approvers`? `016-intent-planning` and `017-intent-approval` need the same answer.
- Should GitHub aliases stay accepted for every verb, or should the GitHub projection become write-only for some of them
  (for example `cancel`)?
- Should `retry` on a `Failed` intent re-run the failed stage only, or start again from planning?
- Should `revise` from the status page require a note, so the round input always has human feedback?
