---
id: "015"
slug: intent-stage-runtime
title: "In-pod plan and build stages with report repair, working notes and run records"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 3
area: intents
effort: high
status: proposed
depends_on:
  - 002-no-credentials-in-agent-pods
  - 004-claude-posture-hardening
  - 007-artifact-contract
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/intent.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/repair.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/idle.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentrun/trees.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/envelope/envelope.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/plan.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/build.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/report/section.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/agentresult/plan.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/prompt_plan.md.tmpl"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/templates/prompt_repair.md.tmpl"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/e2e/intent_repair_test.go"
  - "https://github.com/devthenet-labs/maul/commit/2073d28d861d7965a56f7cd1416741882cb464f5"
  - "https://github.com/devthenet-labs/maul/commit/92ffea23749652c10ea44b4038c787ec3f8b020e"
  - "https://github.com/devthenet-labs/maul/commit/d103b9f2a6d604cdc157f891f094690a14226729"
  - "https://github.com/devthenet-labs/maul/commit/b74acc5ccff8be1d7f83ba68ab914d9a0dfd2461"
  - "https://github.com/devthenet-labs/maul/commit/e0f71a26108504b34ff1a2f73de94a46bdad3b8e"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/design/intent-driven-development.md#plan-contract-and-output-sanitisation"
issue: https://github.com/bitwise-media-group/intents/issues/16
---

# [patchy] In-pod plan and build stages with report repair, working notes and run records

## What should change, and why?

After this lands, `agent-runner` can run the two agent stages of an intent on their own, from fixtures and from the e2e
harness, without any intent controller. The plan stage (`PATCHY_PHASE=plan`) reads an intent request that was pinned in
git by commit and digest, runs read-only, and writes only `reports/plan.md`. The build stage (`PATCHY_PHASE=build`)
receives only an approved plan, runs with workspace write, and returns a verified changeset. A malformed report is
repaired in the same agent session instead of throwing the work away. Every terminal event carries a canonical run
record that a controller can archive as markdown in git, so nothing about a run lives only in truncated CR status.

This is the runtime core that intent planning (`016-intent-planning`) and building (`018-intent-build-pr`) launch. maul
feeds the same stages a snapshot of a GitHub issue and keeps their output in CR status. Here the input is a git blob and
the output is a record shaped by the artifact contract (`007-artifact-contract`). The pod never writes to git or a
forge, and it never holds a credential: intents run only on brokered harnesses.

Scope:

- Port `internal/agentrun/intent.go` from the pre-rename tree: `runIntent`, `intentHarness`, `planLimits`,
  `buildLimits`, `plan` and `build`. Keep the brokered-only rule: an unbrokered claude or codex, or any copilot harness,
  ends the stage with a `fatal` event before any agent starts.
- Add the envelope `plan` event type (`envelope.TypePlan` and `envelope.Plan`). The build stage keeps reporting as
  `remediation`, since its changeset payload is the same.
- Validate plans with the plan parser that `007-artifact-contract` adds in `api/artifacts/v1` (maul's `ParsePlan` and
  `ParsePlanInput`, moved there with the visible-text and layout rules). Port `internal/report/build.go` and
  `section.go` for the build report and its sections. Do not keep a second copy of the plan or visible-text rules.
- Change the request source. A trusted init container fetches the intents repository tree from the artifact server by
  artifact digest (reusing the `internal/agentrun/trees.go` fetch path), extracts the file at the pinned path, checks
  its sha256 and writes only the body (frontmatter stripped by the 007 parser) to `input/request.md`. A mismatch fails
  the init before the agent container starts.
- Build input: the approved plan arrives as `input/plan.md` and must pass `ParsePlanInput`. The build is handed no
  request: a non-empty `input/request.md` is a `fatal` event. Port `commit.sh` handling, `verifyCommitted` and changeset
  packaging from the remediation stage, so the outcomes `commit_failed` and `changeset_too_large` apply.
- Enforce the plan stage's write scope (commit `d103b9f2`): the claude plan posture from `004-claude-posture-hardening`
  writes only under `reports/`, and the plan is told its own turn and token budget.
- Codex is allowed for the build stage when brokered. For the plan stage its read-only posture is prompt-only, so it is
  refused unless the Job sets `PATCHY_INTENT_CODEX_PLAN=true`, which the controller sets only from an operator flag. The
  run record then states `read_only: prompt-only`.
- Port `internal/agentrun/repair.go`: at most two repair rounds, resumed in the same session within the stage's limits.
  A repair round on the build stage may not change the committed tree.
- Port the idle watchdog (`internal/agentrun/idle.go`) so a run that makes no progress ends with `timeout`.
- Working notes: the build report contract keeps a `Working notes` section (`report.WorkingNotesHeading`). The stage
  copies it into the run record, cut at 6 KiB. Both stages accept an optional `input/context.md` (previous plan, last
  failure, earlier notes), pinned by its own digest, which a controller supplies for replans and rounds.
- Run record: add a `record` block to each terminal event with stage, harness, model, posture, image digest and source,
  network mode, base SHA, request or plan sha256, report sha256, changeset digest, repair rounds used, outcome and
  CLI-reported usage with `usage.source: reported`. Add `report.RenderRunRecord`, which renders it as a `runs/<run>.md`
  file in the 007 run-record shape. The controller archives it; the pod only prints it.

## How will we know it is done?

- [ ] `internal/agentrun` stage-table tests pass for: brokered claude plan, brokered claude build, brokered codex build,
      codex plan refused without `PATCHY_INTENT_CODEX_PLAN`, unbrokered claude refused with a `fatal` event naming
      `PATCHY_BROKER_TOKEN_FILE`, and copilot refused.
- [ ] Golden invocation testdata exist for the plan stage (read-only, writes under `reports/` only) and for a build with
      one repair round, matching maul's `invocation_build_repair.txt` in shape.
- [ ] An e2e scenario on the fake-kubelet harness runs a plan Job with the fake harness whose first report is invalid.
      It is repaired in-session, the event outcome is `ok`, there is one transcript, and `record.repair_rounds` is 1.
- [ ] An e2e scenario whose pinned request sha256 does not match the fetched file fails in the init container. The agent
      container never starts and no transcript exists.
- [ ] A unit test hands the build stage a non-empty `input/request.md` and gets a `fatal` event. A plan with a bidi
      control character in its body ends `report_invalid` after two repair rounds.
- [ ] `report.RenderRunRecord` output for plan and build fixtures passes the 007 validator, and its `report_sha256`
      equals the sha256 of the report bytes in the event.
- [ ] A plan-stage fixture whose agent writes outside `reports/` is refused, and the outcome says why.

## Isolation invariants

- **No credentials in agent pods:** both stages call `intentHarness` first and refuse any harness that is not brokered
  through `002-no-credentials-in-agent-pods`. The request and the plan reach the pod as files, never with a forge token.
  No new Secret is mounted.
- **Broker-only egress:** the stages add no egress destination. The init fetches the request from the in-cluster
  artifact server, the same path trees use today. Model traffic goes only to the broker.
- **Custom resources for state, git for artifacts, GitHub as projection:** the pod emits the run record on stdout and
  never writes to git, blob storage or a forge. A controller archives it through `006-durable-records`. The request is
  read from a git blob pinned by digest, not from a GitHub issue.

## Out of scope

- The intent controller, the CRDs, planning triggers and approval (`016-intent-planning`, `017-intent-approval`).
- The records writer and its storage backend (`006-durable-records`).
- Running the build in a repository-declared image (`013-repository-image-execution`); here builds use the default
  image.
- Revise and check-fix prompts and the compare-patch handoff (`019-intent-review-rounds`), multi-repository trees
  (`020-intent-multi-repo`), agent resource classes (018) and live command-output streaming (025 reads it from
  `pods/log`).

## Depends on

- `002-no-credentials-in-agent-pods`: brokered claude and codex, so `intentHarness` has something to accept.
- `004-claude-posture-hardening`: the hardened read-only and workspace-write claude postures the stages render.
- `007-artifact-contract`: the plan parser and visible-text rules in `api/artifacts/v1`, the request parser that strips
  frontmatter, and the run-record shape that `RenderRunRecord` must produce.

## References

- `devthenet-labs/maul@86a3f567^`: `internal/agentrun/intent.go`, `repair.go`, `idle.go`, `trees.go`, `config.go`.
- `internal/envelope/envelope.go` (`TypePlan`, `Plan`), `internal/agentresult/plan.go`.
- `internal/report/plan.go` and `visible.go` (moved by 007), `build.go`, `section.go` (`WorkingNotesHeading`).
- `internal/templates/prompt_plan.md.tmpl`, `prompt_build.md.tmpl`, `prompt_repair.md.tmpl`.
- `internal/agentrun/testdata/invocation_build_repair.txt`, `e2e/intent_repair_test.go`.
- Commits `2073d28d` (in-pod plan and build stages), `92ffea23` (report repair), `d103b9f2` (plan budget and write
  scope), `b74acc5c` (idle watchdog), `e0f71a26` (brokered codex intents).
- `docs/design/intent-driven-development.md#plan-contract-and-output-sanitisation`.
- `docs/configuration/agent-runner.md`.

## Open questions

- Should codex ever plan intents? Its read-only posture is enforced only by the prompt. The proposal is an operator flag
  that is off by default, with the posture stated in the run record and on the projected plan.
- The run record carries CLI-reported usage, which a repository image can forge. Should the pod leave usage out
  entirely, so only the controller fills `usage` from `009-broker-spend-limits` measurements, or emit it as `reported`
  for the controller to replace?
- The request digest covers the whole file, but the planner reads only the body. Is that acceptable, or should the
  frontmatter be visible to the planner as context (it names dependencies and repositories)?
- Should the intent input files be renamed (`input/request.md`, `input/plan.md`) or keep maul's `issue.md` and
  `investigation.md` names to share code with Finding stages?
- Do repair rounds count against the stage's turn budget, or get a small separate allowance?
