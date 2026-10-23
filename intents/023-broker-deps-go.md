---
id: "023"
slug: broker-deps-go
title: "Fetch Go modules through an authenticated broker dependency route"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 4
area: broker
effort: high
status: proposed
depends_on:
  - "003-broker-only-agent-network"
  - "009-broker-spend-limits"
  - "013-repository-image-execution"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/egress-proxy.md#routes"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/egress-proxy.md#go-registries"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/deployment/isolation.md#network-profiles-the-go-dependency-route"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/egressproxy/path.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/egressproxy/gorepo.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/netprofile"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/httpguard"
  - "https://github.com/devthenet-labs/maul/commit/611729e0332ac59bce07de93f7a8356c29580185"
issue: https://github.com/bitwise-media-group/intents/issues/24
---

# [patchy] Fetch Go modules through an authenticated broker dependency route

## What should change, and why?

Once this lands, a Finding remediation (and later an intent build) running in a repository's Go image can fetch a newly
tagged module that is not in the image's baked module cache, without the image changing and without any new egress path.
The `go` command talks to a GOPROXY-protocol route on the egress broker. The broker authenticates the calling pod,
checks the run's package grant, serves only tagged releases of granted module prefixes from `proxy.golang.org` (and
`sum.golang.org` for checksums) or from an operator's Artifactory or Nexus Go repository, and records every fetch
against the run. The plan prompt and the stage prompt state which modules the run can fetch.

maul serves this from a separate egress-proxy whose identity is "the port": no token is checked, it has its own internet
egress and audit format, and it carries an opaque CONNECT tunnel. That fails "agent egress goes only through the egress
broker". patchy folds the Go route into the broker as a protocol-aware, read-only route family that shares the broker's
front end: pod-bound projected token checked by TokenReview, pod UID check, attribution, budget, one audit schema and
one kill switch. This is the first dependency route; `024-broker-deps-npm-pypi` reuses the framework.

Scope:

- Add a `deps` mode to `cmd/egress-broker`, deployed as a second Deployment (`<release>-egress-deps`) of the same binary
  with its own ServiceAccount, NetworkPolicy and credential mounts. Registry parsing and large bodies never share a
  process with model credentials. The deps mode reuses `internal/broker`'s pre-auth limits, TokenReview with a dedicated
  audience, the pod UID and annotation read, budget and attribution keys, and audit writer.
- Port the GOPROXY route from `internal/egressproxy` (`path.go`, `gorepo.go`, `upstream.go`, `dial.go`, `echo.go`,
  `redirect.go`) and the grammar and grant types from `internal/netprofile` (`module.go`, `grant.go`, `registry.go`,
  `denied.go`) into `internal/broker/deps`. Keep path-element prefix matching, refusal of `golang.org/toolchain`, the
  tagged-release gate with opt-in `allowPseudoVersions`, the 410-on-refusal and 503-on-overload rules, and response
  header and size checks. Port `internal/httpguard` for the dialer that refuses non-public and non-443 addresses.
- Registry credentials for Artifactory and Nexus Go repositories are mounted only into the deps Deployment, polled for
  rotation, sent only to the registry's exact origin, and scanned for echo in every non-archive response.
  `privateModules` become `GONOSUMDB` and are never looked up in `sum.golang.org`. Prefer short-lived tokens minted by
  the broker's workload identity over static Secrets.
- Grants: an operator `DependencyPolicy` custom resource lists the allowed upstreams, registries and module prefixes per
  repository selector. The job controllers stamp a `patchy.bitwisemedia.uk/dependency-grant` annotation on
  repository-image Jobs, fenced by a ValidatingAdmissionPolicy so only they can set it. The broker reads it with the
  UID-checked pod read and refuses any pod without one.
- Pod authentication: the Job gets a projected token for the deps audience with a TTL of the Job deadline plus 15
  minutes. `GOAUTH` runs the injected `/patchy/bin/agent-runner goauth` helper, which reads the token file and prints an
  `Authorization` header for the deps origin only.
- TLS: the deps route serves HTTPS only, from a chart-managed CA whose bundle the trusted `prepare` container places
  under `/patchy/ca`. Plaintext requests are refused, so no token crosses the network in clear.
- Controller-owned Go env on repository-image Jobs, replacing image values: `GOPROXY` (the deps route, then the baked
  cache, with no `direct` or `off`), `GOSUMDB`, `GONOSUMDB`, `GOPRIVATE`, `GOINSECURE` and `GONOPROXY` set non-empty,
  `GOENV=off`, `GOTOOLCHAIN=local`, `GOMODCACHE=/tmp/go/pkg/mod`, and `SSL_CERT_FILE`.
- Spend and audit: each fetch counts against the run's byte and request budget in the broker ledger from
  `009-broker-spend-limits`. The audit line uses the broker's schema with route family `deps.go`. The settled run's
  record lists every fetched `module@version` with its `h1:` hash.
- Kill switch: `egressBroker.deps.suspend: true` makes the route answer `410 suspended` and stops the job controllers
  stamping grants from the next Job.
- Changeset check: refuse any changeset whose file paths or contents name the deps host, so lockfiles keep canonical
  URLs.

## How will we know it is done?

- [ ] Ported unit tests for the Go path grammar, module matching, version gate, registry route and dialer pass under
      `internal/broker/deps`.
- [ ] An e2e scenario: a remediation on a Go image with a grant for `github.com/google/uuid` runs
      `go get github.com/google/uuid@<new tag>` and `go test ./...` successfully. The image's baked cache does not
      contain that version.
- [ ] An e2e scenario: a module outside the grant gets 410, the build falls through to the baked cache, and the audit
      line names the run, the pod and the refusal reason.
- [ ] An e2e scenario: a request with no token, an expired token, a token for another audience, or from a pod without a
      grant annotation is refused before any upstream contact.
- [ ] An e2e scenario: setting `egressBroker.deps.suspend: true` answers `410 suspended` to a Job that is already
      running.
- [ ] An envtest shows the admission policy denies a Pod that sets `dependency-grant` from any ServiceAccount other than
      the job controllers'.
- [ ] `helm template` shows the agent NetworkPolicy allows only the artifact server, the broker and the deps Service. It
      fails when deps is enabled without broker TLS, or with a module prefix that admits `golang.org/toolchain`.
- [ ] The archived run record lists each fetched `module@version` and hash, and the registry credential appears in no
      response, pod spec or record.

## Isolation invariants

- **No credentials in agent pods:** registry credentials exist only in the deps Deployment. The pod holds only its
  projected, audience-bound identity token, which the broker checks by TokenReview and pod UID. A registry
  `Authorization` header sent by the agent is dropped.
- **Broker-only egress:** agent pods still reach only broker Services and the artifact server. The deps route is GET and
  HEAD only, protocol-aware and read-only, with no CONNECT tunnel and no publish path. Refusals never contact the
  upstream.
- **Custom resources for state, git for artifacts, GitHub as projection:** `DependencyPolicy` and the grant annotation
  are cluster state. The per-run dependency manifest goes into the durable run record in git. Audit lines go to log
  sinks, not git.

## Out of scope

- npm and PyPI routes (`024-broker-deps-npm-pypi`).
- maul's CONNECT tunnel, network profiles keyed by port, and the separate egress-proxy binary.
- Fetching private modules directly from a forge with a VCS token, and caching modules in blob storage.
- Grants for default-image runs, which have no Go toolchain.

## Depends on

- `003-broker-only-agent-network`: the broker-only agent NetworkPolicy and DNS posture this route must slot into.
- `009-broker-spend-limits`: the broker ledger, per-run budget annotation and measured-usage feed that fetches are
  charged to.
- `013-repository-image-execution`: repository-image Jobs, the injected `/patchy/bin`, the env scrub and the admission
  policy that the grant annotation and Go env extend.

## References

- `docs/configuration/egress-proxy.md`, sections "Routes", "The go environment a profile Job gets", "Go registries" and
  "Credentials", pinned to `devthenet-labs/maul@55b163a8`.
- `docs/deployment/isolation.md`, sections "Network profiles: the Go dependency route" and "Registry grants".
- `internal/egressproxy` (`doc.go`, `path.go`, `gorepo.go`, `registry.go`, `dial.go`, `echo.go`, `redirect.go`).
- `internal/netprofile` (`module.go`, `grant.go`, `registry.go`, `denied.go`) and `internal/httpguard`.
- `internal/broker/budget.go`, `internal/broker/preauth.go` and `internal/broker/audit.go` for the shared front end.
- `e2e/network_profile_test.go` and `e2e/registry_test.go`.
- Commits `82b30634` (httpguard and profiles), `611729e0` (Go route), `b6959207` (registry routes), `6f312bd5` (ending a
  build refused by policy).

## Open questions

- Does a separate deps Deployment of the broker binary count as "the egress broker"? The alternative is one process
  holding model credentials, registry parsers and registry credentials together.
- Can every supported Go version use `GOAUTH` with a command, or is a netrc file under `/tmp`, rewritten when the token
  rotates, needed for older toolchains?
- Should the grant come only from the operator's `DependencyPolicy`, or may an approved plan narrow it to the modules
  the build says it needs?
- Should broker TLS be its own phase 0 intent covering the model routes too, rather than landing here for deps only?
- Where should the dependency manifest live for Finding runs, which have no intent record: the run record alone, or also
  a per-repository index?
