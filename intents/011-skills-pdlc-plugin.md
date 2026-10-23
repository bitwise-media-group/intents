---
id: "011"
slug: skills-pdlc-plugin
title: "Add a pdlc plugin to the skills marketplace for authoring intents and reviewing plans"
project: skills
repositories:
  - https://github.com/bitwise-media-group/skills
phase: 1
area: skills
effort: medium
status: proposed
depends_on:
  - 007-artifact-contract
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/sizing.md"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/plan.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/visible.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#plan-contract-and-output-sanitisation"
issue: https://github.com/bitwise-media-group/intents/issues/12
---

# [skills] Add a pdlc plugin to the skills marketplace for authoring intents and reviewing plans

## What should change, and why?

A person or a coding agent installs the `pdlc` plugin from the bitwise marketplace in Claude Code, Codex CLI,
Antigravity or OpenCode. They can then turn a rough idea into an intent file that meets the artifact contract, break a
large request into dependency-ordered intents that each deliver something usable, and review a planner's plan before
approving it. The skills work on their own, and run `patchy lint intents` when the CLI is on `PATH`.

Intents are only as good as their requests. An approver reads every byte of a plan, and a planner reads bytes the
approver may not see, so requests need an outcome first, observable acceptance criteria, explicit isolation invariants,
a scope that fits one build, and plain visible text. Today that knowledge lives in this repository's README and template
and in maul's design notes. A plugin puts it where authors and agents work, and keeps it aligned with the contract
from 007.

Scope:

- New plugin `plugins/pdlc/` following `plugins/workflow`: `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`
  with the same version (Codex `interface.displayName` and `shortDescription`), `CHANGELOG.md`, and no `hooks/`
  directory.
- Marketplace entries in `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` with an explicit
  `./plugins/pdlc` source, a `plugins/pdlc` package in `release-please-config.json` and `.release-please-manifest.json`,
  and a `pdlc` entry in the `zensical.toml` nav.
- Skill `pdlc-intent`: draft or refine one intent file to the contract. Outcome first, then why, then a concrete scope
  list; 4-10 observable acceptance checkboxes; the three isolation invariants made specific; out of scope; depends on;
  references; open questions. It sizes the intent against the guide (a large build is about 300 agent turns over 90
  minutes) and refuses HTML, HTML comments, `<details>`, emoji and invisible characters. `templates/intent.md` holds the
  shape; `reference.md` holds the rules and worked examples.
- Skill `pdlc-intent-split`: decompose a large request into intents, each with a usable outcome on its own, an effort
  level, and `depends_on` edges that form a DAG. It writes one file per intent from the same template and a short
  ordered list of what each one unblocks.
- Skill `pdlc-plan-review`: review a plan report against its request and the plan contract before approval. It checks
  scope creep beyond the request, hidden or invisible text and layout tricks, new dependencies and network asks,
  repositories outside the request, estimates against the granted budget, and unanswered planner questions. It writes a
  findings list ending in approve, request changes or refuse. `templates/plan-review.md` holds the output shape.
- Command `commands/intent.md` (`/pdlc:intent`) that applies `pdlc-intent` to an argument hint.
- Validation: when `patchy lint intents` is available, each skill runs it on the files it writes and fixes what it
  reports. Without it, the skill applies the checklist in its `reference.md`, which mirrors 007's rules.
- Evals per skill under `plugins/pdlc/evals/<skill>/`: `triggers.json` with 10-20 entries, near-miss negatives included,
  and `evals.json` with 2-5 behavioural evals using deterministic assertions, with fixtures under `files/`.
- Generated docs and evaluation reports (`make docs-gen`, `make report`) committed as the repository requires.

## How will we know it is done?

- [ ] `make lint` passes: markdownlint, evolve Tier 0, eval JSON schemas, licence headers, plugin validate and
      `docs-check` with the new nav entry.
- [ ] `evolve run checks` confirms the Claude and Codex manifests carry the same version.
- [ ] `make triggers` shows each skill activating on its positives and not on near-misses such as "write a GitHub issue
      template", "review this pull request's code" and "plan my sprint".
- [ ] A `pdlc-intent` eval turns a fixture idea into `<project>/<id>/request.md` (007's layout); regex assertions find
      the H1, both required sections, 4-10 checkboxes, the three bolded invariants, and no `<!--`, `<details>` or
      invisible character.
- [ ] A `pdlc-intent-split` eval turns a fixture epic into at least three files whose `depends_on` values name only
      files that exist and contain no cycle (a `command` assertion runs a small checker).
- [ ] A `pdlc-plan-review` eval on a fixture plan with a hidden zero-width span and an unrequested repository reports
      both and does not recommend approval.
- [ ] `install.sh` installs the three skills by symlink, and the docs site renders a `pdlc` plugin page.

## Isolation invariants

- **No credentials in agent pods:** the plugin runs on a workstation or in a coding agent, never in a patchy agent pod.
  Its skills read and write local files and need no token. They tell authors never to put credentials, hostnames or
  internal URLs in an intent.
- **Broker-only egress:** not affected at runtime. `pdlc-plan-review` flags any plan that asks for egress other than the
  broker, such as new hosts, a proxy or a CONNECT tunnel, as a reason to refuse.
- **Custom resources for state, git for artifacts, GitHub as projection:** the skills write intent files to git, never
  to a GitHub issue. They say that the file is the source of truth and the issue is a projection, and they never read an
  issue back into a file.

## Out of scope

- A standalone validator in the plugin. Validation is `patchy lint intents` from 007, or the reference checklist.
- Skills that run, approve or merge anything in patchy.
- Plan authoring; plans are written by patchy's planner, and this plugin only reviews them.

## Depends on

- `007-artifact-contract`: the request and plan schemas, the visible-text rules and the `patchy lint intents` command
  the skills follow and call.

## References

- `docs/intents/sizing.md`: what a feature-sized run consumes, the basis for the sizing guidance.
- `internal/report/plan.go` and `internal/report/visible.go`: the plan frontmatter, bounds and visible-text rules the
  review skill checks.
- `docs/design/intent-driven-development.md`, section "Plan contract and output sanitisation".
- In this repository: `README.md` working assumptions and `templates/intent.md`.
- In `bitwise-media-group/skills`: `AGENTS.md` and `plugins/workflow` as the layout example.

## Open questions

- Plugin and skill names: `pdlc` now, or the post-rebrand product name (033)? Renaming a published plugin breaks
  installs, so deciding before the first release is cheaper.
- Should the templates be vendored copies of 007's schemas and this repository's template, or fetched from a pinned
  patchy release at run time?
- Should `pdlc-plan-review` also review approval records and run records, or stay with plans?
- Is a `/pdlc:review-plan` command worth adding alongside `/pdlc:intent`?
