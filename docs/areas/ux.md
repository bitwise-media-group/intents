---
description: "The intents dashboard, status page and CLI actions, and onboarding."
---

# Operator experience

How people see and steer intents, and how an operator gets from nothing to a working Project.

- **Dashboard** (025). A board of intents by phase, each intent's timeline, and live output from its runs. Requests,
  plans and reports render from the custom resources and their git records, and stay readable after the TTL, without the
  status server ever holding a forge token.
- **Actions** (026). Approve, replan, cancel, revise, suspend and retry from the status page and the CLI, as custom
  resource writes enforced by RBAC custom verbs and admission policy, exactly like today's Finding actions.
- **Onboarding** (027). `patchy setup github-app --intents`, Projects whose intents come from a git repository, records
  and blob configuration, and `patchy check project` until every line passes.

Per-user model credentials have their Account page here too, but live with the broker work that resolves them
([022](../intents/022-per-user-model-credentials.md)).

--8<-- "build/intent-docs/areas/ux.md"
