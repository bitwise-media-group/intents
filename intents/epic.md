---
title: "Agentic PDLC: bring maul's capabilities into patchy without weakening isolation"
issue: https://github.com/bitwise-media-group/intents/issues/1
---

# Agentic PDLC: bring maul's capabilities into patchy without weakening isolation

## Goal

[devthenet-labs/maul](https://github.com/devthenet-labs/maul) is a hard fork of patchy. It extends patchy's security
flywheel into a full agentic product development lifecycle. A human writes an intent, an agent plans it, a human
approves the plan, an agent builds it in the application's own toolchain image and opens the pull request, review
feedback and failing checks start further rounds, and each pull request gets a live preview. maul also adds per-user
model credentials, cost-based spend limits, usage attribution, dependency access for builds, a status dashboard for
intents and an onboarding CLI.

This epic defines the work needed to bring those capabilities into patchy, or a renamed patchy derivative, without
breaking its isolation model. Each sub-issue is one intent: a chunk of work with a usable outcome, defined by a markdown
file under `intents/` in this repository.

## Non-negotiable invariants

- Agent pods never hold credentials: no model keys, forge tokens or cloud credentials.
- Agent pods reach the outside world only through the egress broker. They have no direct internet access, including for
  dependency fetching and including indirect access through a model vendor's server-side tools.
- Custom resources hold state. Durable artifacts (requests, plans, approvals, run reports, usage reports) are kept as
  hard copies in git or blob storage. GitHub issues are a one-way projection.

## What the review of maul found

- **Already compatible:** brokered Claude, the digest-verified repository tarball, the plan contract and its verbatim,
  digest-bound approval, create-only branches, controller-composed commit messages and a single sanitiser for agent
  text.
- **Gaps patchy must close first:** codex pods hold the OpenAI key, copilot pods hold a GitHub token, the broker
  forwards to the full upstream API (so server-side web tools give indirect internet access), the default agent
  NetworkPolicy still allows TCP 443 to anywhere with open DNS, and Claude stages still honour repository-supplied
  `.claude` settings and `.mcp.json`.
- **maul features that break the invariants as built:** the egress-proxy, network profiles and the CONNECT tunnel are a
  second egress path outside the broker. They must become authenticated broker routes before builds can use them.
- **maul features that conflict with git as the source of truth:** maul treats the GitHub issue body as the
  authoritative request and the plan comment as the approval artifact. Its ConfigMaps are deleted with the Intent after
  14 days. Approval must instead bind to a commit SHA and a digest of a plan file in git.
- **Porting cost:** mostly additive. patchy has changed little in these areas since the fork (2026-09-12), apart from
  dependency bumps such as go-github v93, Go 1.27, Preact 11 and the toolchain v3 layout. maul's rename to `maul.run` is
  the main mechanical cost, so ports start from maul's pre-rename tree (`86a3f567^`).

## Phases

0. Isolation floor: harden the broker, broker every harness, lock agent networking, harden Claude postures and build an
   end-to-end harness. Each item improves today's Finding flow.
1. Records, contracts and spend: a durable records writer, the git artifact contract and validator, one command grammar,
   cost-based spend limits, a brand registry, and a skills plugin for authoring intents and reviewing plans.
2. Repository images: pin and run agent stages in the application's own toolchain image, under admission control.
3. Intents: plan, approve, build, review rounds and multi-repository intents, all git-native.
4. Identity and dependencies: run attribution and usage, per-user model credentials, and Go, npm and PyPI through broker
   routes.
5. Operator experience: the intents dashboard, actions from the status page and CLI, and onboarding.
6. Previews: isolated slots, a signed-in gateway, digest-pinned images, previews for intent pull requests, and setup and
   check commands.
7. Rebrand: an in-place, upgradable rename.

## Collaboration

maul's author has agreed to contribute once this work is well defined. The intents are written so that maul itself can
plan and build them: each file's request section is shaped like maul's issue form.
