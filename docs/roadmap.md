---
description: "The eight phases of the work, the intents in each, and the dependency graph between them."
---

# Phases & dependencies

The intents are ordered into phases by their dependencies. A phase does not have to finish before the next starts: an
intent can start as soon as everything it depends on has landed. The phases say what makes sense to do first, and why.

- **Phase 0** closes gaps in patchy as it is today, so each item is worth shipping even if nothing else is.
- **Phases 1 and 2** build what everything later writes through: records, contracts, spend limits, the command grammar
  and repository images.
- **Phase 3** is the intent lifecycle itself.
- **Phases 4 to 7** add identity, dependency access, the operator experience, previews and the rename.

## Dependency graph

An arrow points from an intent to the intents it unblocks.

--8<-- "build/intent-docs/graph.md"

--8<-- "build/intent-docs/roadmap.md"
