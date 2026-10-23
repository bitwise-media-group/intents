---
id: "004"
slug: claude-posture-hardening
title: "Harden claude stage postures and gate CLI bumps on a real-CLI posture probe"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: runtime
effort: medium
status: proposed
depends_on: []
refs:
  - "https://github.com/devthenet-labs/maul/commit/bafe7d7c76c3645b747cb79deb0b3b2ec1a473af"
  - "https://github.com/devthenet-labs/maul/commit/50a45d409337df09024bfeda7196f11d3f632aab"
  - "https://github.com/devthenet-labs/maul/commit/7e49c95d23445d1e050be5eea9b65d57c6d8546e"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/harness/claude.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/harness/claude_probe_test.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/hack/claude-posture-probe.sh"
issue: https://github.com/bitwise-media-group/intents/issues/5
---

# [patchy] Harden claude stage postures and gate CLI bumps on a real-CLI posture probe

## What should change, and why?

After this lands, patchy's claude investigate stage (read-only) and remediate stage (workspace-write) ignore any Claude
Code configuration the repository brings: `.claude/settings.json`, `.claude/settings.local.json` and `.mcp.json`. The
read-only stage has no shell. It can read only inside its workspace and write only to its report directory. Every run
uses a permission mode patchy chooses. On every claude CLI bump, CI runs a probe against the real binary, with a fake
model on loopback, which proves all of this before the bump can merge.

Today `internal/harness/claude.go` allows `Bash(git log:*)`, `Bash(git show:*)`, `Bash(git blame:*)` and
`Bash(git diff:*)` in the read-only posture. It passes no `--setting-sources`, `--permission-mode` or
`--strict-mcp-config`. A hostile repository under investigation can therefore add a `SessionStart` hook that runs a
command, an env block, a `defaultMode` such as `acceptEdits`, or an MCP server. Each of these runs code or grants a tool
that the posture withholds. Flag behaviour drifts between CLI versions. maul probed 2.1.263, and 2.1.291 for resume.
patchy pins 2.1.304 in `Dockerfile.claude-agent-runner`, and renovate bumps it. This intent has no dependencies and
protects the existing Finding pipeline now.

Scope:

- Every postured run gets `--setting-sources user`, `--permission-mode dontAsk`, `--strict-mcp-config` and
  `--add-dir <ws>`, with `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` so the tree's `CLAUDE.md` is still read as
  guidance.
- Read-only posture: `--restricted` with `--tools Read,Glob,Grep,Edit,Write`. `Bash`, `WebFetch`, `WebSearch`, `Task`,
  `NotebookEdit` and `MultiEdit` are denied by name. `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- Path-scoped writes: port `WriteDirs` (`claudeAllow`). In the read-only posture a request with `WriteDirs` swaps the
  bare `Write` allow for one `Edit(//<dir>/**)` rule per directory, which covers Write and Edit alike. Edit stays in
  `--tools` but not in the allow list, because a bare Edit deny removes the tool. The investigate stage sets `WriteDirs`
  to its report directory.
- Workspace-write posture: keep the built-in tool set with `Bash`, plus the pinned setting sources, permission mode and
  strict MCP config.
- Prompts: rewrite the investigation prompt so it no longer offers git shell commands. If investigations need history,
  `prepare` writes a bounded `git log` summary file into the workspace for the agent to read.
- ResumeSpec renders the full posture again, so a later report repair (`015-intent-stage-runtime`) resumes under the
  same rules.
- Probe: port `hack/claude-posture-probe.sh` and `TestClaudePostureProbe`, with its loopback fake upstream and control
  runs. Add a mise task `claude-posture-probe` to `tasks.toml`, and a CI job in `.github/workflows/ci.yaml` that runs
  `--if-changed <base>` when `Dockerfile.claude-agent-runner` or `internal/harness` changes.
- Re-probe at 2.1.304 before merging. Record any flag semantics that changed since 2.1.263 in the harness comments.
- Docs: an "Agent tool postures" section in `docs/deployment/isolation.md`.

## How will we know it is done?

- [ ] `hack/claude-posture-probe.sh` passes against claude 2.1.304. Its control run, with the pins removed, shows every
      trap firing: a repository hook writes a marker, an env block lands, `defaultMode` takes effect, a `.mcp.json`
      server starts, and a read outside the workspace succeeds.
- [ ] Golden argv tests for both postures pin the flags, the tool lists and the env entries.
- [ ] `writedirs` unit tests show `Edit(//<report dir>/**)` replacing the bare `Write` allow, so writes and edits are
      allowed only under that directory.
- [ ] A harness unit test shows the read-only posture has no `Bash` entry in any allow list.
- [ ] In the probe, a read-only run on a fixture tree with a `SessionStart` hook and a `.mcp.json` ends with no hook
      marker and no MCP server process.
- [ ] The CI probe job is skipped on a pull request that leaves the CLI pin and `internal/harness` unchanged. It runs on
      a renovate pull request that bumps `CLAUDE_VERSION`, and fails it if any trap fires.
- [ ] The investigation prompt golden test contains no `git` shell instructions.

## Isolation invariants

- **No credentials in agent pods:** no change. The probe runs the real CLI against a loopback fake model with a
  throwaway placeholder key, so CI needs no model credential.
- **Broker-only egress:** no change to egress. Withholding the shell from the read-only stage and refusing repository
  MCP servers removes in-pod tools that could test the network policy. `--strict-mcp-config` means no MCP server is
  started at all.
- **Custom resources for state, git for artifacts, GitHub as projection:** no change. Stage reports keep flowing through
  the envelope into the run CR as today.

## Out of scope

- Codex postures. Codex's read-only posture is prompt-only, which is tracked in `015-intent-stage-runtime`.
- Report repair and intent plan and build stages (`015-intent-stage-runtime`).
- Managed settings baked into a repository image (013 treats such images as untrusted code).

## Depends on

- None.

## References

- `devthenet-labs/maul@55b163a8`: commits 50a45d40 (pin claude's setting sources), 7e49c95d (narrow the read-only
  posture to the file tools) and bafe7d7c (deny edit tools, pin the permission mode, probe the CLI posture on bumps).
- `internal/harness/claude.go` (`claudeTools`, `claudeRestricted`, `claudeSettingSources`, `claudePermissionMode`,
  `claudeNoAutoMemory`), `internal/harness/claude_probe_test.go`, `internal/harness/writedirs_test.go`.
- `hack/claude-posture-probe.sh`, `tasks.toml` task `claude-posture-probe`, and the `claude-posture-probe` job in
  `.github/workflows/ci.yaml`.
- `docs/deployment/isolation.md`, section "Agent tool postures".

## Open questions

- Losing `git log` and `git blame` may weaken investigations. Is a pre-rendered history file in the workspace enough, or
  do approvers accept the loss?
- If 2.1.304 has changed what `--restricted` or `dontAsk` do, do we pin the CLI back or adapt the posture? Which one
  wins if the probe fails on a security fix release?
- Should the probe also run on a schedule against the latest CLI, to warn before renovate opens the bump?
