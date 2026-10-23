---
description: "Centralised product names and an upgradable rename."
---

# Rebrand

patchy started as an agentic security flywheel and is becoming a full PDLC platform; maul has already renamed itself. A
rename touches the API group, label and annotation keys, environment variable prefixes, branch prefixes, issue markers,
binaries, charts and images. Done carelessly, it strands every existing install.

- **Centralise first** (010). One brand registry holds every product name, with a test that no literal escapes it.
  Nothing visible changes, and every port from maul after it adds names in one place.
- **Rename last** (033). The new API group is installed beside the old one, a `migrate` command copies every object with
  its status under a global agent pause, and both sets of names are accepted for a release before the old ones are
  removed.

Both intents are name-agnostic. The name itself, and whether it is shared with maul, is an open question.

--8<-- "build/intent-docs/areas/rebrand.md"
