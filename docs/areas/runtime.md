---
description: "What runs inside an agent pod: postures, sandbox proofs, network lock-down and repository images."
---

# Agent runtime

What an agent pod is allowed to do, and how patchy proves it is held to that.

- **Postures** (004). Claude stages stop honouring a repository's own `.claude` settings and `.mcp.json`, the read-only
  stage loses its shell, and every Claude CLI bump is gated on a probe against the real binary.
- **Network** (003). Agent pods are locked to the broker and the artifact server, with no DNS, and a probe inside every
  pod proves it before the agent starts.
- **Repository images** (012, 013, 014). A build runs in the application's own toolchain image, so it can run `go test`,
  `npm test` or `pytest`. The image is resolved once to a signed, allowlisted digest. patchy's agent-runner is injected
  read-only, admission policy refuses anything else, and spend limits are required. Application teams get an agent base
  image, examples and `patchy init app` to publish a signed image.

An application-declared image is untrusted code that controls the agent's process environment. The controls in 013 exist
because of that, and must ship before repository images are enabled.

--8<-- "build/intent-docs/areas/runtime.md"
