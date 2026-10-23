---
id: "016"
slug: intent-planning
title: "Plan intents read from git, record plans in git and project them to GitHub issues"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: high
status: proposed
depends_on:
  - 006-durable-records
  - 007-artifact-contract
  - 008-command-vocabulary
  - 015-intent-stage-runtime
  - 009-broker-spend-limits
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/project_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/intent_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/intentrun_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/project_controller.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_plan.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/snapshot.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/replan_context.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/open_prs.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/run_controller.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/intent_issue.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/ttl.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/intent.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/intentperm/intentperm.go"
  - "https://github.com/devthenet-labs/maul/commit/ff30e24afc315cc924bf61f05403d28d9ae14994"
  - "https://github.com/devthenet-labs/maul/commit/4b3c8a99478b62a02224aae4803c6d5515ce622d"
  - "https://github.com/devthenet-labs/maul/commit/5a61f4b10ff3b93ef540709c9e086da66990e7a6"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#end-to-end-flow-slice-1"
issue: https://github.com/bitwise-media-group/intents/issues/17
---

# [patchy] Plan intents read from git, record plans in git and project them to GitHub issues

## What should change, and why?

After this lands, an operator applies a `Project` that points at an intents repository, such as this one. When an intent
request is merged there, patchy creates an `Intent`, pins the request bytes by commit and sha256, runs a brokered
read-only plan, and records the plan as an immutable markdown record in git. The plan is also projected verbatim onto a
tracking issue so people can read and discuss it. Planning is useful on its own: an operator gets reviewed-quality plans
for intents written in git, before any build exists.

maul discovers intents from labelled GitHub issues and treats the issue body as the request and the plan comment as the
approval artifact. Both are lost or mutable once the `Intent` is deleted at TTL. Here git is the source of truth for the
request and the plan, the custom resources hold state, and the GitHub issue is a one-way projection that is never parsed
back into the request.

Scope:

- New binary `cmd/intent-controller`, off by default (`intentController.enabled: false` in `charts/patchy`). Env prefix
  `PATCHY_INTENT_`; flags `--intent-poll-interval`, `--intent-ttl` and the plan stage limits.
- Port the `Project`, `Intent` and `IntentRun` CRDs into `patchy.bitwisemedia.uk/v1alpha1` from the pre-rename tree,
  with these changes. `Project.spec.intents` gains `{repository, path, branch}`. `Project.spec.repositories` is limited
  to one entry (`020-intent-multi-repo` lifts this). `Intent.spec.issue` becomes `spec.source {repository, path, id}`.
  `status.input` becomes `{revision, commit, path, blobSHA, sha256, configMap, contextDigest}` and `status.plan` carries
  `{revision, digest, record {repository, commit, path, blobSHA}, configMap}`. GitHub comment ids move to
  `status.tracking` as projection metadata only.
- Discovery by git, not labels: `ProjectReconciler` watches a source-controller `Repository` for the intents repository
  and reacts when its artifact revision (commit SHA) changes. It walks the `<project>/<id>/request.md` files of the 007
  layout under `Project.spec.intents.path`, validates each with the `007-artifact-contract` parser, creates `Intent`
  `<project>-<id>` for each valid request, and sets a Project condition naming each invalid file. Keep the name budget
  (`<project>-<id>` at most 33 characters).
- Planning authority: a request revision starts planning when the commit that introduced it was merged by an approver
  (`Project.spec.approvers`, write permission, not a bot), or when an approver posts `/patchy plan` on the tracking
  issue. Otherwise the Intent waits in `Pending` with an `AwaitingTrigger` condition. Register the intent issue surface
  (`plan`, `replan`, `cancel`, `import`) in the `internal/command` grammar from `008-command-vocabulary`. An optional
  `/patchy import` on an ordinary issue commits its body as a new `request.md` through the `006-durable-records` git
  backend, and that commit is the intake.
- Pin the request as `{repository, commit, path, sha256}` and hand it to the plan Job as the artifact
  `015-intent-stage-runtime` fetches. Keep an immutable `<intent>-input-r<N>` ConfigMap as the in-cluster cache.
- Port the run scheduler path for plan runs (`IntentRun` stage `plan`, slot pool, `internal/schedule` `Pick`) and the
  plan collection path in `run_controller.go`. Re-derive the plan from the report with `agentresult.FromPlan`.
- Record every plan as `<project>/<id>/plan-r<N>.md`, and the plan run as `runs/<run>.md`, through
  `006-durable-records`. Store the commit, path, blob SHA and sha256 from the receipt in `status.plan.record`. Cache the
  bytes in an immutable `<intent>-plan-r<N>` ConfigMap.
- Replan context: port `replan_context.go` so `context.md` holds the previous plan read from its git record, the last
  failure and earlier working notes. Mirror it to the blob store through 006 and put its digest in the run record, so a
  replan input is reproducible. Port `open_prs.go` so the planner sees other intents' open pull requests, fenced and
  bounded (empty until `018-intent-build-pr` opens any).
- Projection: create or adopt the tracking issue in the intents repository, post the plan with
  `templates.RenderPlanComment` in a code fence no line can close, and keep one status comment edited in place. Edits to
  the issue body never change `status.input`.
- Port `ttl.go` so an ended Intent is deleted only after its records are archived. Port the `intentperm` table, narrowed
  to the grants planning needs, and prove each grant before `Ready`.
- `patchy get projects|intents|intentruns`: phase, plan revision, short record commit and plan digest.

## How will we know it is done?

- [ ] e2e (fake GitHub, fake kubelet): merging `demo/001/request.md` into the intents repository through a pull request
      merged by an approver moves `Intent` `demo-001` through `Pending`, `Planning` and `AwaitingApproval`.
      `status.input.commit` is the merge commit and `status.input.sha256` equals the sha256 of the blob.
- [ ] In the same scenario, `plan-r1.md` exists at `status.plan.record.commit`, its sha256 equals `status.plan.digest`,
      and the tracking issue has exactly one plan comment holding the same bytes.
- [ ] A file merged by a non-approver leaves the Intent `Pending` with `AwaitingTrigger`. `/patchy plan` from an
      approver starts planning. From a non-approver it gets one refusal reply and nothing runs.
- [ ] Editing the tracking issue body changes neither `status.input` nor `status.plan`.
- [ ] A new commit that changes the request while `AwaitingApproval` marks the plan stale (`RequestChanged`). Planning
      restarts only under the planning-authority rule.
- [ ] A plan report with raw HTML or a hidden construct is refused under the 007 rules, gets a refusal notice, and no
      plan record is written as offered.
- [ ] An intent file that fails the 007 validator creates no Intent and sets a Project condition naming the path.
- [ ] envtest: `spec.source` and `spec.project` are immutable (CEL), and `SetIntentPhase` refuses illegal edges.
- [ ] After TTL deletes an ended Intent, its request, plan and run records are still readable at their recorded commits,
      and a TTL test shows deletion waits until records are archived.

## Isolation invariants

- **No credentials in agent pods:** the plan Job is a brokered, read-only `015-intent-stage-runtime` plan stage on the
  default image. All GitHub reads and writes, and all records writes, happen in intent-controller with tokens minted per
  operation for one repository and one permission set.
- **Broker-only egress:** the plan pod reaches only the broker and the artifact server. The request and the trees arrive
  as digest-verified artifacts. No network profile or other egress route is ported.
- **Custom resources for state, git for artifacts, GitHub as projection:** the request is a git blob pinned by commit
  and sha256. The plan and run records are written to git, and the replan context to the blob mirror, by the controller.
  The records repository must be private unless `records.allowPublic` is set. The tracking issue is written, never read
  for content; only authority facts (who merged, who commented, write permission) are read.

## Out of scope

- Approval and the plan pull request surface (`017-intent-approval`).
- Builds, pushes and application pull requests (`018-intent-build-pr`), rounds and multi-repository Projects.
- Status page views and actions (`025-intents-dashboard`, `026-intent-actions`).
- Previews, network profiles, attribution, per-user credentials, usage rollups and resource classes.

## Depends on

- `006-durable-records`: the controller-side writer that commits plan and run records, the blob mirror, and the archived
  marker that gates TTL.
- `007-artifact-contract`: the request parser, the `<project>/<id>/` layout, the `<project>-<id>` identity and the
  visible-text rules for plans.
- `008-command-vocabulary`: the `/patchy plan|replan|cancel|import` grammar, the authority check and the sanitiser.
- `015-intent-stage-runtime`: the plan stage, the envelope `plan` event and the run record.
- `009-broker-spend-limits`: the per-run cost budget annotation and broker-measured usage that plan stage limits reuse.

## References

- `devthenet-labs/maul@86a3f567^`: `api/v1alpha1/project_types.go`, `intent_types.go`, `intentrun_types.go`.
- `internal/controller/intent/project_controller.go`, `intent_plan.go`, `snapshot.go`, `replan_context.go`,
  `open_prs.go`, `run_controller.go`, `intent_issue.go`, `ttl.go`.
- `internal/templates/intent.go` (`RenderPlanComment`, `PlanMarker`), `internal/intentperm/intentperm.go`.
- `cmd/intent-controller/serve.go`, `docs/configuration/intent-controller.md`, `e2e/intent_test.go`.
- Commits `ff30e24a` (CRDs), `4b3c8a99` (slice 1a controller), `5a61f4b1` (context across replans).
- `docs/design/intent-driven-development.md#end-to-end-flow-slice-1` and `#ending-an-intent-and-its-name`.

## Open questions

- Planning authority: is "merged by an approver" enough to spend on a plan, or must every plan start from an explicit
  `/patchy plan`? Should the frontmatter `status` gate discovery (for example only `ready`)?
- What happens when a merged `request.md` is deleted from the intents repository: cancel the Intent, or leave it running
  and only stop replans?
- Approvers: GitHub logins in `Project.spec.approvers`, Kubernetes subjects, or both? `017-intent-approval` and
  `026-intent-actions` need the same answer.
- The 007 layout puts `plan-r<N>.md` beside `request.md`, which implies the records repository configured in 006 is the
  intents repository. Is that required, or may a Project send its records to a separate private repository?
- Should the controller create the tracking issue, or adopt the `issue` URL from the frontmatter and refuse to plan
  until a human sets it?
- Approver comments on the tracking issue are replan feedback in maul. Keep reading them (fenced, approver-only,
  unedited, mirrored with the replan context), or require feedback to arrive as commits to the intent file?
