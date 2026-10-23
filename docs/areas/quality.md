---
description: "The end-to-end harness that proves the other intents work."
---

# Quality

Almost every intent's acceptance criteria end in an end-to-end scenario. patchy's e2e suite drives real controller
binaries under envtest against a fake GitHub, but it cannot run an agent Job's pod. maul's fake kubelet can: it runs
each Job's pod with a fake agent, and the real API server proxies its logs.

This intent lands that harness first, on today's Finding flow, so that every later intent can prove itself the same way.

--8<-- "build/intent-docs/areas/quality.md"
