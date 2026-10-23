---
id: "021"
slug: run-attribution-usage
title: "Attribute every agent run to a verified principal and report usage"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 4
area: broker
effort: high
status: proposed
depends_on:
  - 009-broker-spend-limits
  - 006-durable-records
  - 018-intent-build-pr
refs:
  - "https://github.com/devthenet-labs/maul/commit/b03c4a29f5f84f86a4d57aadd960c005b00d98d4"
  - "https://github.com/devthenet-labs/maul/commit/19e1c55361a4dcdab3c464843c991cc08406a0f8"
  - "https://github.com/devthenet-labs/maul/commit/d05931bd8f9b53111fa2f7a103945980bd11d863"
  - "https://github.com/devthenet-labs/maul/commit/e7498e4af4d660dd2b7b14236d8b7c731612e487"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/attribution"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/usagerollup"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/usageview"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/attribution-policy.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/attribution.md"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/intent_attribution_test.go"
issue: https://github.com/bitwise-media-group/intents/issues/22
---

# [patchy] Attribute every agent run to a verified principal and report usage

## What should change, and why?

Every Investigation, Remediation, IntentRun and EvaluationUnit records, once and immutably, the principal it ran for and
why. Admission policies prove that only the run controllers set it. Each run's measured usage from 009 is folded,
exactly once, into durable `UsageRollup` objects by principal, by principal and Project, and by Project. A signed-in
user sees their own usage on a Usage page in the status server, holders of `usage/all` see everyone's, and
`patchy get usage --user <principal> --project <name> --since 30d` prints the same figures. A monthly usage report is
written as markdown through 006, so a cluster rebuild loses nothing.

Per-user spend limits and per-user credentials (022) need a trustworthy "who". maul keys it to GitHub numeric ids taken
from issue comments and events, and falls back to the organisation for approvals made on the status page or in the CLI.
In patchy custom resources are the truth and GitHub is a projection (working assumption 3), so approvals made through
the CLI or status page (017, 026) must attribute to a person too. maul's rollups live only in etcd, which breaks the
hard-copy requirement.

Scope:

- Principal model in a new `internal/principal` package. A principal is `org`, `github-id:<n>` for a GitHub-sourced
  action (a plan PR review, a `/patchy` command from 008), or `oidc:<digest>` where the digest is a base32 sha256 of the
  OIDC issuer and subject. An action through the Kubernetes API maps the admission `userInfo` to `oidc:<digest>` when
  the username carries the configured OIDC prefix (chart values `attribution.oidc.issuer` and
  `attribution.oidc.usernamePrefix`). Anything else is attributed to `org` with reason `approver-unregistered` or
  `submitter-unregistered`. Logins and display names are kept for display only.
- Port `spec.attributedTo` (`principal`, `display`, `reason`) to the four run kinds from
  `devthenet-labs/maul@86a3f567^`, immutable by CEL, and the `patchy.bitwisemedia.uk/attributed-to` annotation on every
  agent Job and pod template.
- Attribution table, adapted from maul: investigation `org`; remediation the Finding's approver when held; intent plan
  the requester; intent build and check-fix the plan's approver from 017's approval record; revise the approver whose
  command or review started it; evaluation unit the Evaluation's `spec.submitter`.
- Port `charts/maul/templates/attribution-policy.yaml` as up to six fail-closed ValidatingAdmissionPolicies: only run
  controllers set the annotation and `spec.attributedTo`, investigation-controller only ever writes `org`, and the value
  matches the principal pattern. Chart value `attribution.mode` (`off`, `record`, `attribute`).
- Port `internal/usagerollup` (the run finalizer and exactly-once ledger), the `UsageRollup` CRD with day and month
  buckets, and `internal/usageview` as the single projection behind the page and the CLI.
- status-server: `GET /api/usage` and a Usage view (`UsageView.tsx` on preact 11) behind `statusServer.usage.enabled`,
  gated by SubjectAccessReview on the virtual `usage/self` and `usage/all` subresources.
- CLI: `patchy get usage` with `--user`, `--project` and `--since` (days, a duration or a first day), reading
  UsageRollups with the caller's kubeconfig.
- Monthly report: on the first day of each month remediation-controller renders `usage/<YYYY-MM>.md` (totals by Project
  and principal, trusted versus reported, price table version) and writes it through 006.
  `patchy records verify usage/<YYYY-MM>` checks it.
- The broker reads the attribution annotation for its audit line only; it authorises nothing yet.

## How will we know it is done?

- [ ] envtest (ported `attribution_policy_envtest_test.go`): a Job created by a non-controller ServiceAccount with the
      annotation is refused, investigation-controller cannot write anything but `org`, and `spec.attributedTo` cannot be
      changed after create.
- [ ] e2e: a Finding approved with `patchy approve finding <name>` by an OIDC-prefixed user has its Remediation
      attributed to that user's `oidc:` principal with reason `approver`, not `org`.
- [ ] e2e: an intent plan approved through 017's CLI path attributes the build IntentRun (018) to the approver, and its
      usage lands in the user, user-project and project rollups exactly once across a forced controller restart.
- [ ] Unit test: a username without the OIDC prefix maps to `org` with reason `approver-unregistered`.
- [ ] `patchy get usage --user <principal> --since 30d` matches `GET /api/usage` for the same window, shown by a shared
      usageview projection test.
- [ ] A tier without `usage/all` sees only its own principal on the Usage page and gets 403 for another user's.
- [ ] After the month rolls over in e2e (fake clock), `usage/<YYYY-MM>.md` exists in the records repository and
      `patchy records verify` passes on it.

## Isolation invariants

- **No credentials in agent pods:** no pod gains anything. The attribution annotation is an identifier, not a
  credential, and the VAPs stop a prompt-injected agent or any pod creator from billing someone else.
- **Broker-only egress:** unchanged. The broker reads the annotation from the caller pod it already inspects for budgets
  (009) and records it in the audit line.
- **Custom resources for state, git for artifacts, GitHub as projection:** attribution lives on run specs and rollups
  are custom resources. Monthly reports are hard copies in git and blob storage, written by a controller through 006.
  GitHub ids are accepted as authority facts for GitHub-sourced actions only; nothing is attributed on a login alone.

## Out of scope

- Per-user credentials paying for runs, and the Account page (022).
- Per-user spend limits enforced at the broker.
- Billing or chargeback exports to finance systems.
- A mapping CR that links one person's GitHub id and OIDC subject into one principal.

## Depends on

- `009-broker-spend-limits`: measured, priced usage on every run, which the rollups fold.
- `006-durable-records`: the writer for the monthly usage report.
- `018-intent-build-pr`: build IntentRuns to attribute, and (through `017-intent-approval`) approval records that carry
  the approver's principal for CLI, status page and plan-PR approvals.

## References

- `commit b03c4a29` feat: attribute every agent run to a person (#224).
- `commit 19e1c553` feat: durable per-user usage rollups (#230).
- `commit d05931bd` feat(status): usage page, API and CLI (#233), and `commit e7498e4a` (#250).
- `internal/attribution`, `internal/usagerollup`, `internal/usageview`, `api/v1alpha1/usagerollup_types.go`.
- `internal/web/usage.go`, `internal/web/ui/src/components/UsageView.tsx`, `cmd/maul/internal/cli/usage.go`.
- `charts/maul/templates/attribution-policy.yaml` and `charts/maul/attribution_policy_envtest_test.go`.
- `docs/configuration/attribution.md`, sections "What is recorded", "Admission policies" and "Usage rollups".
- `e2e/intent_attribution_test.go`.

## Open questions

- Principal model: is `oidc:<digest>` from the status page issuer the right canonical identity, or should it be the raw
  Kubernetes username, or GitHub numeric ids with a mapping from OIDC?
- Should a person's GitHub-sourced and OIDC-sourced actions be linked into one principal now (a mapping CR), or later
  with 022?
- Is a hashed principal in a private records repository acceptable for the monthly report, or should reports show
  display names?
- Should the Usage page wait for 025's hardened envelope, or ship with today's status-server envelope since it is
  read-only?
