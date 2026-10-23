---
id: "000"
slug: short-kebab-slug
title: "Imperative one-line title, at most 100 characters"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: broker
effort: medium
status: proposed
depends_on: []
refs: []
issue: null
---

# [patchy] Imperative one-line title, at most 100 characters

## What should change, and why?

One or two paragraphs stating the outcome in terms of what an operator, approver or agent can do once this lands, and
why it matters. Name the isolation invariant it protects or relies on.

Scope:

- The concrete pieces of work, each a sentence. Name packages, binaries, CRDs, chart values and CLI commands where they
  are known.

## How will we know it is done?

- [ ] Observable acceptance criteria: a unit, envtest or e2e test that proves the behaviour, a CLI command and its
      output, a chart render guard, a dashboard view.

## Isolation invariants

- **No credentials in agent pods:** how this intent keeps it.
- **Broker-only egress:** how this intent keeps it.
- **Custom resources for state, git for artifacts, GitHub as projection:** how this intent keeps it.

## Out of scope

- What a planner might reasonably include but must not.

## Depends on

- `NNN-slug`: the capability this intent needs from it.

## References

- maul paths, commits and design sections to port from or learn from, pinned to `devthenet-labs/maul@55b163a8` (or
  `86a3f567^` for pre-rename names).

## Open questions

- Decisions the approver must make before or while approving the plan.
