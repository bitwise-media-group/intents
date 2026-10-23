---
description: "The shape of an intent file, how big an intent should be, and how it projects onto an issue."
---

# Writing intents

An intent says what should change and how everyone will know it is done. It does not say how to build it: that is the
planner's job, and the approver judges the plan against the intent.

## The file

Each intent is `intents/<id>-<slug>.md`, started from
[`templates/intent.md`](https://github.com/bitwise-media-group/intents/blob/main/templates/intent.md):

```markdown title="intents/017-intent-approval.md (abridged)"
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
issue: https://github.com/bitwise-media-group/intents/issues/18
---

# [patchy] Approve a plan by binding to its commit and digest, from a plan PR, the CLI or a command

## What should change, and why?

## How will we know it is done?

## Isolation invariants

## Out of scope

## Depends on

## References

## Open questions
```

- **The frontmatter** is metadata for people and tooling. It is not part of the request a planner reads. `refs` lists
  prior art as full permalinks pinned to a commit (a file, a commit or a design section), so each one says which
  repository and revision it means without the schema naming any product.
- **The request** is everything after it. The H1 and the first two sections are the fields of maul's per-project issue
  form, so the request projects onto an issue unchanged. Do not add a `Repositories` section: the intent controller
  appends the Project's repositories itself.

## What makes a good intent

- **Outcome first.** Open with what an operator, approver or agent can do once it lands, then why it matters, then a
  concrete scope list naming packages, binaries, custom resources, chart values and CLI commands.
- **Observable acceptance.** Four to ten checkboxes, each something a reviewer can see: a named test, CLI output, a
  chart render that fails, an end-to-end scenario.
- **Invariants made specific.** Say how this intent keeps each of the three invariants, not that it does.
- **One build.** It must deliver something usable on its own and fit one feature-sized build: maul's sizing guide puts a
  large build at about 300 agent turns over 90 minutes. Split anything larger, and connect the parts with `depends_on`.
- **Plain, visible text.** No HTML, HTML comments, `<details>` blocks, emoji or invisible characters. An approver reads
  every byte, and a planner reads bytes the approver may not see.
- **Open questions are honest.** List the decisions the approver must make. A plan built on a silent assumption is
  harder to review than one that names it.

## Effort

Effort is how much agent work a build takes, not how long a person would take. T-shirt sizes do not map onto agentic
builds, so intents use the three values of the organisation's Effort issue field:

| Effort | Meaning                                                                                       |
| ------ | --------------------------------------------------------------------------------------------- |
| low    | A focused change in one package and its tests, well inside the default build budget           |
| medium | One feature across a few packages, or a chart change with render guards                       |
| high   | A feature-sized build near maul's large preset (about 300 turns over 90 minutes): a subsystem |

An intent that would need more than high effort is too big for one build: split it, or say in its scope how the planner
should split it.

## Checks

`make lint` runs the intent validator (`scripts/check_intents.py`) over every file. It checks the frontmatter keys and
their order, the file name, the H1, the sections and their order, effort levels, phases and areas, that dependencies
exist, sit in the same or an earlier phase and appear in the `Depends on` section, that there are no cycles, and that
the request holds no raw HTML or invisible characters.

## Projection

`make project` renders each intent as an issue in this repository: it creates or updates the issue, adds it to the
[project board](https://github.com/orgs/bitwise-media-group/projects/3), sets its Effort issue field and its Area field
on the board, links it as a sub-issue of the tracking epic, records `blocked by` dependencies, and writes the issue URL
back into the file. It never reads an issue back into an intent. To change an intent, change the file.
