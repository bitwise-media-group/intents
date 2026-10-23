---
description: "Every open question the intents leave for an approver, grouped by area."
---

# Open questions

Each intent ends with the decisions its approver must make. They are collected here, grouped by area, so the ones that
cut across several intents are easy to spot. Answer a question by changing the intent file: either fold the decision
into its scope, or move it to `Out of scope`.

Some questions recur across areas, and settling them early unblocks the most work:

- **Approver identity.** Are approvers GitHub logins, Kubernetes subjects, or both? It affects
  [016](intents/016-intent-planning.md), [017](intents/017-intent-approval.md),
  [021](intents/021-run-attribution-usage.md), [026](intents/026-intent-actions.md) and
  [027](intents/027-intents-operator-onboarding.md).
- **Where records live.** In the intents repository, a dedicated records repository or branch, or blob storage first? It
  affects [006](intents/006-durable-records.md), [007](intents/007-artifact-contract.md) and
  [016](intents/016-intent-planning.md).
- **Broker TLS.** No intent yet owns TLS for the broker's model routes. [023](intents/023-broker-deps-go.md) adds it for
  dependency routes, whose tokens sit in package-manager configuration.
- **A global agent pause.** It sits in [027](intents/027-intents-operator-onboarding.md), but the Finding flow could use
  it now, and [033](intents/033-rebrand-api-migration.md) depends on it.
- **The product name.** [011](intents/011-skills-pdlc-plugin.md) publishes a plugin and
  [033](intents/033-rebrand-api-migration.md) renames everything. Deciding the name before either ships is cheaper.

--8<-- "build/intent-docs/questions.md"
