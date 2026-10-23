---
description: "Plan, approve, build and revise intents, git-native from request to merge."
---

# Intent lifecycle

The heart of the work: an intent goes from a merged request file to a merged pull request, with a human approving the
exact plan in between. It follows maul's design closely, with one deliberate change. maul treats the GitHub issue as the
request and the plan comment as the approval artifact. Here the request and the plan are files in git, the approval
binds to a commit and a digest, and the issue is a projection. See
[Git as the source of truth](../concepts/source-of-truth.md).

The lifecycle runs in a new, opt-in `intent-controller` with three custom resources: `Project` (operator config),
`Intent` (one per request, with its phase machine) and `IntentRun` (one immutable child per agent attempt). The intents
here build it up in usable steps:

- a command grammar and authority rule that the Finding flow benefits from first (008);
- the in-pod plan and build stages, testable without the controller (015);
- planning, then approval, then building, each usable on its own (016, 017, 018);
- bounded revision and check-fix rounds (019), then multi-repository intents (020).

Key decisions carried by these intents:

- **The build receives only the approved plan.** The plan's bytes are re-hashed against the approval when the run is
  created and again at launch, and the request itself is never shown to the build agent.
- **Branches are never force-moved.** The first push creates a branch; every revision fast-forwards it, so human commits
  on a pull request survive.
- **Network profiles are not ported.** Builds get dependency access only through the broker's routes
  ([023](../intents/023-broker-deps-go.md), [024](../intents/024-broker-deps-npm-pypi.md)).

--8<-- "build/intent-docs/areas/intents.md"
