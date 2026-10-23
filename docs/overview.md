---
description: "Why this work exists, what the review of maul found, and how the intents are organised."
---

# The work effort

[patchy](https://github.com/bitwise-media-group/patchy) began as an agentic security flywheel: scanner alerts become
`Finding` resources, an agent investigates each one, and a second agent opens a pull request for the ones it can fix.
[maul](https://github.com/devthenet-labs/maul), a hard fork of patchy, extends that machinery into a full agentic
product development lifecycle (PDLC):

1. A human writes an **intent**: the change they want and how they will know it is done.
2. An agent reads the code, with no shell and no network, and writes a **plan**.
3. A human **approves** exactly that plan.
4. An agent **builds** it in the application's own toolchain image and opens the pull request.
5. Review feedback and failing checks start bounded **revision rounds**.
6. Each pull request gets a live, signed-in **preview** until it merges.

maul also adds per-user model credentials, cost-based spend limits, usage attribution, dependency access for builds, a
status dashboard for intents and an onboarding CLI.

This site defines the work needed to bring those capabilities into patchy, or a renamed patchy derivative, without
weakening the isolation model that patchy is built on. maul's author has agreed to contribute once the work is well
defined.

## The invariants

Every intent keeps three rules. They are explained in full under [Isolation model](concepts/isolation.md) and
[Git as the source of truth](concepts/source-of-truth.md).

- **Agent pods hold no credentials:** no model keys, forge tokens or cloud credentials.
- **Agent pods reach the outside world only through the egress broker:** no direct internet access, including for
  dependency fetching, and no indirect access through a model vendor's server-side tools.
- **Custom resources hold state, git holds artifacts, GitHub is a projection:** requests, plans, approvals and run
  reports are kept as hard copies in git or blob storage, and GitHub issues are a one-way view of them.

## What the review of maul found

Five reviewers read maul against patchy's `main`, each covering one area: the intent lifecycle, the agent runtime,
egress and credentials, previews, and the operator experience.

- **Already compatible.** Brokered Claude, the digest-verified repository tarball, the plan contract with its verbatim,
  digest-bound approval, create-only branches, controller-composed commit messages and a single sanitiser for agent text
  all fit patchy's model as they are.
- **Gaps patchy must close first.** Codex pods hold the OpenAI key and Copilot pods hold a GitHub token. The broker
  forwards to the full upstream API, so a model vendor's web tools give agents indirect internet access. The default
  agent NetworkPolicy still allows TCP 443 to anywhere, with open DNS. Claude stages still honour repository-supplied
  `.claude` settings and `.mcp.json`. [Phase 0](roadmap.md#phase-0-isolation-floor) closes these, and each fix improves
  today's Finding flow.
- **maul features that break the invariants as built.** maul's egress-proxy, network profiles and CONNECT tunnel are a
  second way out of an agent pod, beside the broker. They become authenticated, inspectable broker routes before any
  build may use them ([023](intents/023-broker-deps-go.md), [024](intents/024-broker-deps-npm-pypi.md)).
- **maul features that conflict with git as the source of truth.** maul treats the GitHub issue body as the
  authoritative request and the plan comment as the approval artifact, and its copies are deleted with the `Intent`
  after 14 days. Here approval binds to a commit SHA and a digest of a plan file in git
  ([016](intents/016-intent-planning.md), [017](intents/017-intent-approval.md)).
- **Porting cost.** The work is mostly additive. patchy has changed little in these areas since the fork on 2026-09-12,
  apart from dependency bumps such as go-github v93, Go 1.27, Preact 11 and the toolchain v3 layout. maul's rename to
  `maul.run` is the main mechanical cost, so ports start from maul's pre-rename tree (`86a3f567^`).

## How the work is organised

The work is split into [intents](catalogue.md). Each one delivers a usable outcome on its own and fits one feature-sized
build. They are grouped two ways:

- **By area**, under _Areas_ in the navigation: what part of the system an intent changes. Start here to understand a
  subsystem end to end.
- **By phase**, on the [roadmap](roadmap.md): the order dependencies allow. Start here to plan who picks up what next.

Every intent is also an issue in [bitwise-media-group/intents](https://github.com/bitwise-media-group/intents/issues),
linked as a sub-issue of the [tracking epic](https://github.com/bitwise-media-group/intents/issues/1) and tracked on the
[Agentic Product Development Lifecycle](https://github.com/orgs/bitwise-media-group/projects/3) board. The issues are
projections: the intent files are the source of truth.

## A likely rebrand

patchy is growing well beyond a security flywheel, and maul has already renamed itself. The last phase
([033](intents/033-rebrand-api-migration.md)) renames the product in place with an upgrade path for existing installs.
It is name-agnostic, and an early brand registry ([010](intents/010-brand-registry.md)) keeps every product name in one
package so that the rename touches one place.
