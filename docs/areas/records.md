---
description: "Durable git and blob hard copies, and the schemas every artifact follows."
---

# Records and contracts

Custom resources are deleted after a TTL, and GitHub comments can be edited. Everything worth keeping (requests, plans,
approvals, run reports, image provenance, preview lifecycles and usage) is written as an immutable record instead: a
markdown file in git, with a content-addressed blob mirror for large or sensitive artifacts such as transcripts.

- The **records writer** (006) is controller-side, never in a pod. It commits through the Git Data API with create-only
  refs or fast-forwards, and an ended resource is deleted only after its records are confirmed written. It proves itself
  first on today's Finding flow, by archiving investigation and remediation reports.
- The **artifact contract** (007) defines versioned schemas for requests, plans, run records and approvals, the
  repository layout, the visible-text rules that requests must keep too, and `patchy lint intents` with a reusable CI
  check. This repository follows an early form of it.

Records repositories are private by default, and records use the same public-wording renderers as the dashboard. See
[Git as the source of truth](../concepts/source-of-truth.md).

--8<-- "build/intent-docs/areas/records.md"
