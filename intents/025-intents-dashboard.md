---
id: "025"
slug: intents-dashboard
title: "Show intents on the status page from custom resources and their git records"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 5
area: ux
effort: high
status: proposed
depends_on:
  - 005-e2e-agent-pods
  - 016-intent-planning
  - 006-durable-records
refs:
  - "https://github.com/devthenet-labs/maul/commit/6fb7725292f25e208f46bcf2cb46448f40b0fe5b"
  - "https://github.com/devthenet-labs/maul/commit/6e4ce854b5a978cfcc723538f9f10f8657880c4d"
  - "https://github.com/devthenet-labs/maul/commit/b7a73364bb2a07f43339324a427446b727d2d950"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/intents.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/intents_wire.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/intents_stream.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/envelope.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/authz/project.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/intentview"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/status_intents_test.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/dashboard.md"
issue: https://github.com/bitwise-media-group/intents/issues/26
---

# [patchy] Show intents on the status page from custom resources and their git records

## What should change, and why?

With `statusServer.intents.enabled`, a signed-in user sees a board of intents grouped by phase, each intent's timeline,
and a panel per run with live command output over SSE. Access is decided per Project by SubjectAccessReview on two
virtual subresources. The request, plan and run report views render from the custom resources while they exist and from
the git records afterwards. Each view shows its hard copy: repository, commit SHA, path and sha256. An intent whose
custom resource has passed its TTL can still be opened by name. The whole status page moves to maul's hardened browser
envelope.

The status page is the main human surface for intents. maul's dashboard is read-only, which is right, but it treats the
GitHub issue snapshot as the request and reads plans from ConfigMaps that are deleted at TTL. In patchy the custom
resource holds state and git holds the artifacts (working assumption 3), so the views must show the git record and link
to it, and must keep working after the custom resource is gone without giving status-server a forge token.

Scope:

- Port from `devthenet-labs/maul@86a3f567^`, renamed to patchy: `internal/web/intents.go`, `intents_wire.go`,
  `intents_stream.go`, `internal/intentview` (board columns, public wording, limits) and
  `internal/web/authz/project.go`.
- Read tiers on virtual subresources of `projects.patchy.bitwisemedia.uk`: `get` on `projects/intents` for the board,
  timelines and run panels; `get` on `projects/transcripts` as well for request, plan and report text, transcripts and
  live output. Unauthorised intents are 404, not 403.
- Request view: the request at its recorded commit from 016 (`repository`, `commit`, `path`, `sha256`), replacing maul's
  issue snapshot. The projected issue is shown as a plain link only.
- Records read API: the controller that hosts the 006 writer serves a read-only listener
  (`GET /records/v1/{kind}/{owner}/{revision}`) on a separate port. It authenticates callers by a projected token with
  audience `patchy-records` and TokenReview, admits only status-server's ServiceAccount, reads by digest from the blob
  mirror (or from git with a per-operation read token), re-checks the sha256 and returns the bytes with their receipt.
  status-server uses it for plans and reports when the ConfigMap or custom resource is gone.
- Post-TTL lookup: `GET /api/intents/{name}` falls back to the records index for an ended intent, showing its request,
  plans, approval and run records read-only, marked as archived.
- Port the UI components `IntentsArea`, `IntentsBoard`, `IntentTimeline`, `RunPanel`, `LiveOutput` and `PlainText` to
  patchy's preact 11 bundle and theme, with node `--test` unit tests.
- Hardened envelope for the whole server: port `internal/web/envelope.go` (Sec-Fetch-Site refusal of same-site and
  cross-site on `/api` and `/events`, missing header refused on writes, CSP with hashed inline scripts, HSTS) and maul
  #67's `__Host-` cookie migration of `patchy-auth` and `patchy-oauth2-state`.
- Helm: `statusServer.intents.enabled`, RBAC for `pods/log` in the agents namespace and for reading Projects, Intents
  and IntentRuns, NetworkPolicy egress from status-server to the records read port only, and example Roles for both
  tiers.
- Metrics: open streams, stream refusals by reason, tier-2 reads, and records API reads by result.
- Docs: `docs/status-ui.md` intents section, adapted from maul's `docs/intents/dashboard.md`.

## How will we know it is done?

- [ ] e2e `TestStatusServerIntents` on the 005 harness creates a Project and Intent, runs a plan Job, and asserts the
      board, detail, plan and run endpoints return the expected JSON for a tier-2 user, and 404 for tier-0 and tier-1
      users where text is withheld.
- [ ] e2e: after the plan ConfigMap is deleted, `GET /api/intents/{name}/plans/1` still returns the plan text from the
      records API, with its commit SHA and sha256.
- [ ] e2e: after the Intent custom resource passes its TTL, `GET /api/intents/{name}` returns the archived request, plan
      and approval marked as archived.
- [ ] A records API test refuses a token with the wrong audience or from another ServiceAccount, and refuses to return
      bytes whose sha256 does not match the receipt.
- [ ] A stream test shows live output lines arriving while the fake agent prints, and the stream ending with `revoked`
      within 20 s of removing the user's RoleBinding.
- [ ] Envelope tests: a same-site POST and a POST without Sec-Fetch-Site are refused, the CSP header hashes the embedded
      scripts, cookies are `__Host-` prefixed, and an old `patchy-auth` cookie is ignored.
- [ ] UI unit tests for board, timeline and run panel pass on preact 11, and the board renders in light and dark themes
      in a browser check.
- [ ] A render guard test confirms status-server's Deployment mounts no forge or cloud credential Secret.

## Isolation invariants

- **No credentials in agent pods:** agent pods are untouched. status-server holds no forge token and no blob store
  credential; archived text comes through the in-cluster records API, and external links are for the user's own browser
  to follow.
- **Broker-only egress:** agent egress is unchanged. status-server gains one in-cluster egress rule, to the records read
  port, and nothing on the internet. Live output is read from `pods/log` through the API server.
- **Custom resources for state, git for artifacts, GitHub as projection:** the board comes from custom resources, and
  text comes from the custom resource or its git record, verified by sha256. The GitHub issue is only a link and is
  never read.

## Out of scope

- Any write action: approve, replan, cancel, revise, suspend and retry are 026.
- The Usage and Account pages (021 and 022).
- Live token or dollar figures during a run.
- A full-text search over archived intents.

## Depends on

- `005-e2e-agent-pods`: the fake-kubelet harness that runs plan Jobs and serves `pods/log` for the stream tests.
- `016-intent-planning`: the Project, Intent and IntentRun custom resources and the request and plan records the views
  render.
- `006-durable-records`: the `Reader`, the blob mirror and the receipts the records API serves and verifies.

## References

- `commit 6fb77252` feat: read-only intents dashboard, first slice (#130).
- `commit 6e4ce854` feat: stream a running command's output live in the run panel (#136).
- `commit b7a73364` fix(web): bind status authentication cookies to their host (#67).
- `internal/web/intents.go`, `intents_wire.go`, `intents_stream.go`, `envelope.go`, `tailhub.go`,
  `internal/web/authz/project.go`, `internal/intentview`.
- `internal/web/ui/src/components/IntentsBoard.tsx`, `IntentTimeline.tsx`, `RunPanel.tsx`, `LiveOutput.tsx`.
- `e2e/status_intents_test.go` and `docs/intents/dashboard.md`, section "Two read tiers, per Project".

## Open questions

- Records API or links only: is an in-cluster read API acceptable, or should status-server render only outbound links to
  the records repository and let the user's browser and GitHub access decide?
- Which binary serves the records API: whichever hosts the 006 writer, or a dedicated records reader with read-only
  access?
- Should tier names stay `projects/intents` and `projects/transcripts`, or become plain `read` and `content` tiers ahead
  of the rebrand?
- How far back should post-TTL lookup reach: every archived intent, or only those still listed in a bounded index?
