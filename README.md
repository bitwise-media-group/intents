# intents

Product intents for the Bitwise Media Group agentic product development lifecycle (PDLC): the work needed to bring the
capabilities of [devthenet-labs/maul](https://github.com/devthenet-labs/maul), a hard fork of
[patchy](https://github.com/bitwise-media-group/patchy), into patchy (or a renamed patchy derivative) without weakening
patchy's isolation model.

- **Read it:** [oss.bitwisemedia.uk/intents](https://oss.bitwisemedia.uk/intents/), every intent grouped by area, with
  the roadmap, the dependency graph and the open questions (built from `docs/` and the intent files; `make serve`
  previews it locally).
- **Track it:** [Agentic Product Development Lifecycle](https://github.com/orgs/bitwise-media-group/projects/3), where
  each intent's projected issue carries its Area (a project field) and its Effort (an issue field).

## How intents work here

Every intent is a markdown file under [`intents/`](intents/). **The file is the source of truth.** The GitHub issue it
is projected to is a human-facing view for discussion, assignment and project tracking. It is never parsed back into the
intent. This mirrors how patchy treats a `Finding` and its tracking issue today, and how the intents themselves propose
patchy should treat intents and plans (see `016-intent-planning` and `017-intent-approval`).

An intent file has two parts:

- **YAML frontmatter.** Metadata for people and tooling: `id`, `slug`, `title`, `project`, `repositories`, `phase`,
  `area`, `effort`, `status`, `depends_on`, `refs` (permalinks to prior art, pinned to a commit) and `issue` (the URL of
  the projected issue). It is not part of the request a planner reads.
- **The request.** Everything after the frontmatter: an H1 title (`# [<project>] <title>`), then the sections
  `What should change, and why?` and `How will we know it is done?`. These are the two fields of maul's per-project
  issue form, so the body projects onto an issue unchanged. Supporting sections follow: `Isolation invariants`,
  `Out of scope`, `Depends on`, `References` and `Open questions`. Do not add a `Repositories` section: maul's
  intent-controller appends the project's repositories to the request itself.

Each intent must deliver a usable outcome on its own and fit one feature-sized build. maul's sizing guide puts a large
build at about 300 agent turns over 90 minutes. Split anything larger. Write the request in plain, visible text: no HTML
comments, `<details>` blocks, emoji or invisible characters. An approver reads every byte, and a planner reads bytes the
approver may not see.

Effort is `low`, `medium` or `high`: how much agent work a build takes, matching the organisation's Effort issue field.
T-shirt sizes do not map onto agentic builds.

Start a new intent from [`templates/intent.md`](templates/intent.md). The issue form in
[`.github/ISSUE_TEMPLATE/intent.yml`](.github/ISSUE_TEMPLATE/intent.yml) is a convenience for drafting. An intent
becomes authoritative when its file is merged here.

## Tasks

The repository consumes the shared [toolchain](https://github.com/bitwise-media-group/toolchain) as the `.mise/`
submodule (python archetype), so `make <task>` and `mise run <task>` are interchangeable. Run
`git submodule update --init` and `mise trust --all` once per clone.

```sh
make lint      # licence headers, ruff, workflows, prose, the intent contract and generated-docs drift
make test      # pytest over scripts/
make serve     # the docs site on http://localhost:8004
make project   # project the intents onto issues and the board (needs gh with the repo and project scopes)
make pr        # the full local gate before a pull request
```

Everything reads the intent files through `scripts/intentlib.py`: the validator (`scripts/check_intents.py`), the docs
generator (`scripts/gen_docs.py`, which also writes the index below) and the projection (`scripts/project_issues.py`).

## Working assumptions

These decisions shape every intent. Each one is restated, with the open questions it leaves, in the intents it affects.

1. **Agent pods hold no credentials.** No model keys, forge tokens or cloud credentials, ever. Every harness runs
   through the egress broker. Harnesses that cannot run that way (Copilot, whose credential is a GitHub token) are
   removed from the derivative or refused at render time.
2. **Agent egress goes only through the egress broker.** Agent NetworkPolicy names only the broker and the artifact
   server: no TCP 443 to anywhere and no cluster DNS. Dependency fetching (Go modules, npm, PyPI) becomes a set of
   authenticated, inspectable route families on the broker. They may run as a separate Deployment of the same broker
   binary, with its own ServiceAccount and registry credentials but the same pod authentication, policy, budgets and
   audit; that Deployment counts as the broker. maul's separate egress-proxy and its opaque CONNECT tunnel are not
   ported as they stand, and no route authenticates a pod by source IP alone. Model-vendor server-side tools that reach
   the internet (web fetch, web search, code execution, remote MCP) are refused at the broker.
3. **Custom resources hold state, git holds artifacts, GitHub is a projection.** Requests, plans, approvals, run reports
   and usage reports are written as markdown hard copies to a git repository, with a content-addressed blob mirror for
   large or sensitive artifacts such as transcripts. The writer is a controller, never an agent pod. An approval binds
   to `{repository, commit SHA, path, sha256}` of the plan bytes, not to a GitHub comment. GitHub labels and `/patchy`
   comments stay accepted as aliases that write the custom resource, after an authority check.
4. **Records repositories are private by default.** Plans and reports are permanent once they are in git history. A
   public records repository is refused unless an operator explicitly allows it.
5. **Port under patchy's names, rebrand afterwards.** Work is ported from maul's pre-rename tree
   (`devthenet-labs/maul@86a3f567^`) under patchy's module path, API group and prefixes. Names are first centralised in
   a brand registry (`010-brand-registry`), and the rename itself ships last as a staged, upgradable migration
   (`033-rebrand-api-migration`).

## Contributing

The author of maul has agreed to contribute once this work is well defined. To pick up an intent, comment on its issue,
then open a pull request against the repositories its frontmatter names. To refine an intent, open a pull request that
changes its file here, then run `make project` once it merges. The projected issue is updated from the file, never the
other way round.

## Roadmap

The intent index below is generated from each file's frontmatter (`id`, `title`, `area`, `effort` and `depends_on`).

<!-- index:start -->

### Phase 0: Isolation floor

| ID  | Intent                                                                                                                 | Area          | Effort | Depends on | Issue                                                         |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ------------- | ------ | ---------- | ------------------------------------------------------------- |
| 001 | [Make the egress broker a model-inference chokepoint, not an open proxy](intents/001-broker-chokepoint.md)             | Egress broker | high   | none       | [#2](https://github.com/bitwise-media-group/intents/issues/2) |
| 002 | [Run every harness through the broker so no agent pod holds a credential](intents/002-no-credentials-in-agent-pods.md) | Egress broker | medium | 001        | [#3](https://github.com/bitwise-media-group/intents/issues/3) |
| 003 | [Lock agent pods to broker-only egress and prove it from inside every pod](intents/003-broker-only-agent-network.md)   | Agent runtime | medium | 002        | [#4](https://github.com/bitwise-media-group/intents/issues/4) |
| 004 | [Harden claude stage postures and gate CLI bumps on a real-CLI posture probe](intents/004-claude-posture-hardening.md) | Agent runtime | medium | none       | [#5](https://github.com/bitwise-media-group/intents/issues/5) |
| 005 | [Run agent Job pods end to end in e2e with a fake kubelet](intents/005-e2e-agent-pods.md)                              | Quality       | medium | none       | [#6](https://github.com/bitwise-media-group/intents/issues/6) |

### Phase 1: Records, contracts and spend

| ID  | Intent                                                                                                                             | Area                  | Effort | Depends on | Issue                                                           |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------- | ------ | ---------- | --------------------------------------------------------------- |
| 006 | [Write durable markdown hard copies of run artifacts to git and blob storage](intents/006-durable-records.md)                      | Records and contracts | high   | 005, 007   | [#7](https://github.com/bitwise-media-group/intents/issues/7)   |
| 007 | [Define the git artifact contract for intents, plans and run records, with a validator](intents/007-artifact-contract.md)          | Records and contracts | medium | none       | [#8](https://github.com/bitwise-media-group/intents/issues/8)   |
| 008 | [One /patchy command grammar with write-permission authority and a single agent-text sanitiser](intents/008-command-vocabulary.md) | Intent lifecycle      | medium | 005        | [#9](https://github.com/bitwise-media-group/intents/issues/9)   |
| 009 | [Cost-based run budgets and broker-measured usage on every run](intents/009-broker-spend-limits.md)                                | Egress broker         | high   | 001, 006   | [#10](https://github.com/bitwise-media-group/intents/issues/10) |
| 010 | [Centralise every product name behind a brand registry ahead of a rebrand](intents/010-brand-registry.md)                          | Rebrand               | medium | none       | [#11](https://github.com/bitwise-media-group/intents/issues/11) |
| 011 | [Add a pdlc plugin to the skills marketplace for authoring intents and reviewing plans](intents/011-skills-pdlc-plugin.md)         | Authoring skills      | medium | 007        | [#12](https://github.com/bitwise-media-group/intents/issues/12) |

### Phase 2: Repository images

| ID  | Intent                                                                                                                              | Area          | Effort | Depends on    | Issue                                                           |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------ | ------------- | --------------------------------------------------------------- |
| 012 | [Resolve, verify and pin repository-declared agent images in source-controller](intents/012-repository-image-pinning.md)            | Agent runtime | high   | 005           | [#13](https://github.com/bitwise-media-group/intents/issues/13) |
| 013 | [Run agent stages in the pinned repository image behind trusted injection and admission](intents/013-repository-image-execution.md) | Agent runtime | high   | 012, 003, 009 | [#14](https://github.com/bitwise-media-group/intents/issues/14) |
| 014 | [Agent base image, example images and patchy init app for application teams](intents/014-repository-owner-toolkit.md)               | Agent runtime | medium | 012, 013      | [#15](https://github.com/bitwise-media-group/intents/issues/15) |

### Phase 3: Intents

| ID  | Intent                                                                                                                       | Area             | Effort | Depends on              | Issue                                                           |
| --- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------ | ----------------------- | --------------------------------------------------------------- |
| 015 | [In-pod plan and build stages with report repair, working notes and run records](intents/015-intent-stage-runtime.md)        | Intent lifecycle | high   | 002, 004, 007           | [#16](https://github.com/bitwise-media-group/intents/issues/16) |
| 016 | [Plan intents read from git, record plans in git and project them to GitHub issues](intents/016-intent-planning.md)          | Intent lifecycle | high   | 006, 007, 008, 015, 009 | [#17](https://github.com/bitwise-media-group/intents/issues/17) |
| 017 | [Approve a plan by binding to its commit and digest, from a plan PR, the CLI or a command](intents/017-intent-approval.md)   | Intent lifecycle | medium | 016                     | [#18](https://github.com/bitwise-media-group/intents/issues/18) |
| 018 | [Build an approved plan into a pull request on a create-only branch and archive the outcome](intents/018-intent-build-pr.md) | Intent lifecycle | high   | 017, 013                | [#19](https://github.com/bitwise-media-group/intents/issues/19) |
| 019 | [Revise and check-fix rounds on intent pull requests, fast-forward only and bounded](intents/019-intent-review-rounds.md)    | Intent lifecycle | high   | 018                     | [#20](https://github.com/bitwise-media-group/intents/issues/20) |
| 020 | [Plan once and build across several repositories for one intent](intents/020-intent-multi-repo.md)                           | Intent lifecycle | high   | 019                     | [#21](https://github.com/bitwise-media-group/intents/issues/21) |

### Phase 4: Identity and dependencies

| ID  | Intent                                                                                                            | Area          | Effort | Depends on    | Issue                                                           |
| --- | ----------------------------------------------------------------------------------------------------------------- | ------------- | ------ | ------------- | --------------------------------------------------------------- |
| 021 | [Attribute every agent run to a verified principal and report usage](intents/021-run-attribution-usage.md)        | Egress broker | high   | 009, 006, 018 | [#22](https://github.com/bitwise-media-group/intents/issues/22) |
| 023 | [Fetch Go modules through an authenticated broker dependency route](intents/023-broker-deps-go.md)                | Egress broker | high   | 003, 009, 013 | [#24](https://github.com/bitwise-media-group/intents/issues/24) |
| 024 | [Fetch npm packages and PyPI distributions through broker dependency routes](intents/024-broker-deps-npm-pypi.md) | Egress broker | high   | 023           | [#25](https://github.com/bitwise-media-group/intents/issues/25) |

### Phase 5: Operator experience

| ID  | Intent                                                                                                                              | Area                | Effort | Depends on    | Issue                                                           |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ------ | ------------- | --------------------------------------------------------------- |
| 022 | [Let people pay for their runs with their own model keys, injected only by the broker](intents/022-per-user-model-credentials.md)   | Egress broker       | high   | 021, 002, 025 | [#23](https://github.com/bitwise-media-group/intents/issues/23) |
| 025 | [Show intents on the status page from custom resources and their git records](intents/025-intents-dashboard.md)                     | Operator experience | high   | 005, 016, 006 | [#26](https://github.com/bitwise-media-group/intents/issues/26) |
| 026 | [Approve, replan, cancel, revise, suspend and retry intents from the status page and CLI](intents/026-intent-actions.md)            | Operator experience | high   | 025, 017      | [#27](https://github.com/bitwise-media-group/intents/issues/27) |
| 027 | [Take an operator from nothing to a Ready intent Project with setup and check commands](intents/027-intents-operator-onboarding.md) | Operator experience | high   | 018, 014, 006 | [#28](https://github.com/bitwise-media-group/intents/issues/28) |

### Phase 6: Previews

| ID  | Intent                                                                                                                 | Area     | Effort | Depends on    | Issue                                                           |
| --- | ---------------------------------------------------------------------------------------------------------------------- | -------- | ------ | ------------- | --------------------------------------------------------------- |
| 028 | [Isolated preview slots and a preview-controller on any NetworkPolicy-enforcing cluster](intents/028-preview-slots.md) | Previews | high   | 003           | [#29](https://github.com/bitwise-media-group/intents/issues/29) |
| 029 | [Signed-in, edge-agnostic access to previews through a hardened gateway](intents/029-preview-gateway.md)               | Previews | high   | 028           | [#30](https://github.com/bitwise-media-group/intents/issues/30) |
| 030 | [Digest-pinned, registry-neutral preview images with archived build provenance](intents/030-preview-image-supply.md)   | Previews | medium | 028, 006, 012 | [#31](https://github.com/bitwise-media-group/intents/issues/31) |
| 031 | [Deploy a preview for every open intent pull request and record it in git](intents/031-preview-intent-projection.md)   | Previews | medium | 028, 030, 018 | [#32](https://github.com/bitwise-media-group/intents/issues/32) |
| 032 | [Set up and verify previews with patchy setup previews and patchy check previews](intents/032-preview-setup-check.md)  | Previews | high   | 029           | [#33](https://github.com/bitwise-media-group/intents/issues/33) |

### Phase 7: Rebrand

| ID  | Intent                                                                                                      | Area    | Effort | Depends on         | Issue                                                           |
| --- | ----------------------------------------------------------------------------------------------------------- | ------- | ------ | ------------------ | --------------------------------------------------------------- |
| 033 | [Rename the product with an in-place, upgradable API group migration](intents/033-rebrand-api-migration.md) | Rebrand | high   | 010, 005, 006, 027 | [#34](https://github.com/bitwise-media-group/intents/issues/34) |

<!-- index:end -->
