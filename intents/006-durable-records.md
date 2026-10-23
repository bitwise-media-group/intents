---
id: "006"
slug: durable-records
title: "Write durable markdown hard copies of run artifacts to git and blob storage"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 1
area: records
effort: high
status: proposed
depends_on:
  - 005-e2e-agent-pods
  - 007-artifact-contract
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/push.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/ghclient/refs.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/intent/ttl.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/intentview/doc.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/transcriptstore"
issue: https://github.com/bitwise-media-group/intents/issues/7
---

# [patchy] Write durable markdown hard copies of run artifacts to git and blob storage

## What should change, and why?

An operator points patchy at a private records repository and, optionally, a blob store. From then on every Finding that
reaches a terminal phase has its investigation and remediation reports committed to that repository as immutable
markdown, and mirrored to the blob store under their sha256. The Finding is not deleted by its TTL until that archive
has been written. `patchy records verify finding/<name>` re-reads both copies and checks every digest. The same writer
is the one later intents use for requests, plans, approvals, run records, usage reports and preview records.

Today a Finding's reports live only in `Investigation.status.report`, the Remediation status and the tracking issue. The
rollup loop in remediation-controller deletes the Finding after `remediationController.config.findingTTL` (336h), and
owner references take the reports with it. maul has the same gap for intents: its input and plan ConfigMaps are deleted
with the Intent. Working assumption 3 needs hard copies in git and blob storage, written by a controller and never by an
agent pod. Working assumption 4 needs the records repository to be private unless an operator says otherwise.

Scope:

- New package `internal/records`: a `Writer` interface (`Write(ctx, Record) (Receipt, error)`) and a `Reader` for
  verify. A `Record` is a kind, an owner reference, a revision, a relative path and markdown bytes. A `Receipt` is
  `{repository, commit SHA, path, blob SHA, sha256, blob key}`.
- Git backend over `internal/ghclient`: port maul's split of `CreateCommit` out of `PushBranch` and the create-only and
  fast-forward ref helpers (`CreateBranchRef`, `FastForwardRef`, the 422 sentinel mapping), moved to go-github v93. A
  write builds a tree on the current head, creates one commit and fast-forwards the configured branch. On a
  non-fast-forward it re-reads the head and re-applies the additive commit, up to a bound. It never force-updates a ref
  and never rewrites an existing path: an existing path with the same sha256 is adopted, one with different bytes is an
  error.
- Path guard: every path is controller-chosen, relative, under the configured prefix, free of `..`, and never under
  `.github/**` or named `CODEOWNERS`.
- Blob backend: a content-addressed mirror at `sha256/<digest>` plus a small JSON manifest per record
  (`{kind, owner, revision, repository, commit, path, blobSHA, sha256}`). Adapters for S3, GCS and Azure Blob using the
  controller's workload identity, and a filesystem adapter for dev and e2e. Writes are create-if-absent.
- Record envelope: each markdown file starts with frontmatter `schema`, `kind`, `owner`, `revision`, `sha256` of the
  body and `writtenAt`, followed by the body. Bodies are rendered from controller vocabulary plus verbatim agent
  reports, never from condition messages, pod events or run details (maul's public-wording rule).
- Finding adapter in remediation-controller: on terminal-phase entry, write `findings/<finding>/<n>/investigation.md`
  and `remediation.md` in one commit, then set `status.records` on the Finding (`archivedThrough`, the commit SHA and
  per-file digests). The rollup TTL loop deletes only when `status.records.archivedThrough` equals `status.completedAt`.
  A records outage holds the TTL and sets a `RecordsUnavailable` condition.
- Configuration: chart values `records.git.repository`, `records.git.branch`, `records.git.pathPrefix`,
  `records.allowPublic` (default false), `records.blob.provider` (`s3`, `gcs`, `azure`, `filesystem`, or empty),
  `records.blob.bucket` and `records.blob.prefix`, wired to `PATCHY_RECORDS_*` flags. The `filesystem` provider also
  needs `records.blob.devOnly=true`. Records are off when no repository is set, and TTL behaviour is then unchanged.
- Readiness: remediation-controller proves `contents: write` on the records repository by minting a single-repository
  token at startup. It writes nothing to a public repository unless `records.allowPublic` is true: Findings awaiting
  archive get `RecordsUnavailable` with reason `PublicRepository`, and their TTL holds.
- CLI: `patchy records verify <kind>/<name>` reads the recorded receipts from the CR, fetches the git file and blob with
  the operator's own credentials (`GH_TOKEN`, the cloud default chain), and exits non-zero on any mismatch.

## How will we know it is done?

- [ ] e2e on the 005 harness with fakegithub extended for trees, blobs, commits and refs: a remediated Finding produces
      exactly one commit under `findings/<name>/1/` holding `investigation.md` and `remediation.md`, whose body bytes
      hash to the digests in `status.records`.
- [ ] The same e2e finds `sha256/<digest>` objects and manifests in the filesystem blob backend matching the git blobs.
- [ ] e2e: with the records repository failing, the Finding outlives its TTL, carries `RecordsUnavailable`, and is
      deleted only after the repository recovers and `archivedThrough` is set.
- [ ] `patchy records verify finding/<name>` exits 0, then exits non-zero after the test tampers with the git file and
      again after it tampers with the blob.
- [ ] Unit tests prove the git backend never sends a forced ref update, never writes outside the prefix or under
      `.github/`, adopts an identical existing path and refuses a different one.
- [ ] e2e: pointed at a public repository on fakegithub with `records.allowPublic=false`, the controller writes nothing
      and the Finding carries `RecordsUnavailable` with reason `PublicRepository`.
- [ ] Helm render guard: `records.blob.provider=filesystem` without `records.blob.devOnly=true` fails `helm template`.
- [ ] A golden test shows a record body rendered from a Finding whose conditions carry a node name; the node name does
      not appear in the record.

## Isolation invariants

- **No credentials in agent pods:** agent pods never see the records repository, the blob store or any token for them.
  The git write uses a per-operation, single-repository `contents: write` token minted by remediation-controller. Blob
  writes use the controller's workload identity. No Secret is added to the agents namespace.
- **Broker-only egress:** agent pod egress does not change. All git and blob traffic comes from controller pods over
  their existing forge path and the cloud endpoints that the controller NetworkPolicy already allows or that the chart
  adds for the controller only.
- **Custom resources for state, git for artifacts, GitHub as projection:** the Finding CR stays the state store, and the
  records are write-once archives keyed by digest. Nothing reads records back as state; only verify (and, later, the
  approval check in 017) reads them. The tracking issue stays a one-way projection.

## Out of scope

- Intent, plan, approval, run, usage and preview record kinds. 007 defines their schemas, and 016, 017, 018 to 020, 021,
  030 and 031 write them through this writer. 009 adds a usage block to the Finding records written here.
- Transcripts in records. The blob backend can hold them, but archiving them needs a size and sensitivity review.
- A read API for the status page (025 adds one on top of `Reader`).
- WORM or object-lock retention on the blob store.

## Depends on

- `005-e2e-agent-pods`: the fake-kubelet e2e harness and the fakegithub git data endpoints this intent's e2e uses.
- `007-artifact-contract`: the versioned record envelope and the Finding record kinds this writer emits, so records
  written now validate against the same schemas intents use later.

## References

- `internal/ghclient/push.go` and `internal/ghclient/refs.go` at `devthenet-labs/maul@86a3f567^`: `CreateCommit`,
  create-only and fast-forward refs.
- `internal/controller/intent/ttl.go`: the `RoundNoticesThrough` gate in `wait()`, the pattern for `archivedThrough`.
- `internal/intentview/doc.go`: the public-wording rule records must follow.
- `internal/transcriptstore`: how maul keeps transcripts today, owner-referenced and lost at TTL.
- patchy `internal/artifact/blob.go`: the existing content-addressed blob precedent.

## Open questions

- Where do records live: a dedicated records repository, or the intents repository on its default branch? The second
  needs a ruleset bypass for the GitHub App; a records branch avoids it but is easy to miss.
- Should remediation-controller host the writer, or should a small records-controller own it so only one binary holds
  records write access?
- Is object-lock or WORM retention required on the blob store, or is git history plus content addressing enough?
- Should a Finding's records include the tracking issue's human comments, or only controller and agent text?
- How long should the TTL wait on a records outage before alerting? Holding forever protects the archive but can grow
  etcd during a long outage.
