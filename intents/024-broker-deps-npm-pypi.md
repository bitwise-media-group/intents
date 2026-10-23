---
id: "024"
slug: broker-deps-npm-pypi
title: "Fetch npm packages and PyPI distributions through broker dependency routes"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 4
area: broker
effort: high
status: proposed
depends_on:
  - "023-broker-deps-go"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/egress-proxy.md#registries"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/egress-proxy.md#redirects-and-file-hosts"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/deployment/isolation.md#registry-grants"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/egressproxy/npm.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/egressproxy/pypi.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/egressproxy/pyindex"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/netprofile/pkgname.go"
  - "https://github.com/devthenet-labs/maul/commit/b695920731d013c91861721ca68360254e217b64"
issue: https://github.com/bitwise-media-group/intents/issues/25
---

# [patchy] Fetch npm packages and PyPI distributions through broker dependency routes

## What should change, and why?

Once this lands, a run in a Node or Python repository image can install a package version that is not baked into the
image, using plain `npm install` or `pip install`, from the public registries or from an operator's Artifactory, Nexus
or CodeArtifact repository. Every request goes to a registry-protocol route on the broker's deps Deployment, which
authenticates the pod, applies the run's package grant, keeps registry credentials to itself and records each fetched
`name@version` and digest in the run record. The stage prompt tells the agent which packages the run can fetch.

Node and Python builds are as common as Go in application repositories, and baking every dependency into an image makes
each dependency bump a toolchain release. maul serves npm and pip from its egress-proxy with port-based identity, and
serves other ecosystems only through a CONNECT tunnel whose npm and Yarn hosts are an open publish channel. patchy adds
npm and PyPI as read-only, inspectable route families on the framework from `023-broker-deps-go`, and keeps the tunnel
excluded.

Scope:

- Port the npm route (`internal/egressproxy/npm.go`) into `internal/broker/deps`: packuments (`/<name>` and
  `/@scope%2fname`) and tarballs in the three npm path shapes, GET and HEAD only. Query strings, `dist-tags`,
  `/-/whoami`, version documents, `/-/npm/v1/security/*` and every non-GET method are refused. There is no publish,
  unpublish, login or audit path.
- Port the PyPI route (`pypi.go` and `pyindex/rewrite.go`): `/simple/<project>/` with PEP 503 names, and a rewritten
  simple page whose every link points back to the broker. Links on hosts outside the registry and its `fileHosts`, with
  userinfo or queries, or breaking the wheel, sdist or `.metadata` filename grammar are dropped and counted. Hash
  fragments are kept.
- Keep tarball fetches on the broker. npm runs with `NPM_CONFIG_REPLACE_REGISTRY_HOST=always`, and the broker answers
  only paths under its own origin. Decide during planning whether to also rewrite packument `dist.tarball` URLs as
  defence in depth.
- Port the package-name grammars and grant fields from `internal/netprofile/pkgname.go` and `grant.go`: an explicit
  `packages` allowlist (npm names and `@scope/*`, normalised PyPI names, transitive dependencies included) or an
  explicit `packagePolicy: registry`. Extend `DependencyPolicy` with npm and pypi entries and the switches `scripts`,
  `allowPrerelease` (npm) and `sdists` (pypi), all off by default.
- Registries: `auth.type` `none`, `bearer`, `basic` or `codeartifact` (minted by the deps Deployment's workload
  identity). Redirects are followed only to `redirectHosts`, without the credential. The forge, model-API and cluster
  deny list applies to every registry, file host and redirect host. Credential echo is scanned on every non-archive
  response. Response size caps per kind.
- Pod authentication per client. `agent-runner` writes `/tmp/patchy/npmrc` with the projected token as `_authToken` for
  the deps origin, and points `NPM_CONFIG_USERCONFIG` at it. pip takes the token as `PIP_INDEX_URL` userinfo. Any
  `Authorization` header the agent sends to a registry is replaced, never forwarded.
- Redaction: because the deps token now sits in the npmrc file and the pip index URL, `agent-runner`'s transcript
  redaction and `report.RenderRunRecord` treat the token file's contents as a secret and redact it, including in URL
  userinfo, before any transcript or run record leaves the pod for the 006 writer.
- Controller-owned env on repository-image Jobs, replacing image values: `NPM_CONFIG_REGISTRY`,
  `NPM_CONFIG_IGNORE_SCRIPTS=true` unless granted, `NPM_CONFIG_AUDIT`, `NPM_CONFIG_FUND` and
  `NPM_CONFIG_UPDATE_NOTIFIER` false, `PIP_CONFIG_FILE=/dev/null`, `PIP_INDEX_URL`, a blank `PIP_EXTRA_INDEX_URL` and
  `PIP_FIND_LINKS`, `PIP_ONLY_BINARY=:all:` unless `sdists` is granted, and caches under `/tmp`.
- Every fetch is charged to the run budget, written to the broker audit schema as `deps.npm` or `deps.pypi`, and listed
  in the run record with its integrity hash (`dist.integrity` or the wheel `sha256`).

## How will we know it is done?

- [ ] Ported unit tests for the npm and PyPI path grammars, the name normalisation, the simple-page rewrite, redirect
      handling and credential-echo scanning pass under `internal/broker/deps`.
- [ ] An e2e scenario against a fake npm registry: an allowlisted package installs with `npm install`. A package outside
      the grant gets 403 with a broker reason. A `PUT` (publish) gets 405.
- [ ] An e2e scenario against a fake PyPI index with a separate file host: `pip install` of an allowlisted wheel
      succeeds, an sdist is refused without `sdists`, and the simple page served to the pod links only to the broker.
- [ ] An e2e scenario with a bearer-authenticated registry shows the credential in no response body, header, pod spec,
      env or run record, and that an `Authorization` header sent by the agent is not forwarded.
- [ ] An e2e scenario: a request from a pod without an npm or pypi grant, or without a valid deps token, is refused
      before any upstream contact.
- [ ] `helm template` fails on a registry or file host that is a forge, model API or in-cluster name, on a shared cloud
      suffix in `redirectHosts`, and on a pypi URL not ending `/simple/`.
- [ ] The changeset check refuses a `package-lock.json` or `requirements.txt` that names the deps host.

## Isolation invariants

- **No credentials in agent pods:** registry credentials stay in the deps Deployment and are sent only to the registry's
  exact origin. The pod holds only its audience-bound projected token, which also appears in the npmrc and pip index URL
  that `agent-runner` writes. The transcript and run-record writers redact that token before anything is archived.
- **Broker-only egress:** npm and PyPI are reachable only through GET and HEAD routes the broker parses and judges.
  There is no publish path and no CONNECT tunnel, so npm and Yarn publish hosts are unreachable. File hosts are exact
  names, and redirects never carry a credential.
- **Custom resources for state, git for artifacts, GitHub as projection:** grants live in `DependencyPolicy` and the
  Job's admission-fenced annotation. The dependency manifest is part of the durable run record in git. Audit lines go to
  log sinks.

## Out of scope

- Maven, Gradle, crates, NuGet and OCI routes. These are later route families on the same framework.
- The CONNECT tunnel in any form, and a TLS-terminating broker CA for arbitrary hosts.
- uv, poetry and yarn classic, which write index or tarball URLs into lockfiles. pnpm may work but is not tested.
- Install scripts that download from the internet (`node-gyp` headers, `prebuild-install`), which need baked assets.

## Depends on

- `023-broker-deps-go`: the deps Deployment, shared front end, TLS, token helper, `DependencyPolicy`, grant annotation,
  kill switch, budget charging and manifest plumbing that these routes plug into.

## References

- `docs/configuration/egress-proxy.md`, sections "Grants and package policy", "npm", "pip", "The environment a grant
  gives a Job", "Credentials", "CodeArtifact", "Redirects and file hosts" and "What the chart refuses", pinned to
  `devthenet-labs/maul@55b163a8`.
- `docs/deployment/isolation.md#registry-grants` and `#tunnel-hosts` (the residue this intent avoids).
- `internal/egressproxy` (`npm.go`, `pypi.go`, `pyindex`, `registry.go`, `redirect.go`, `echo.go`, `credential.go`,
  `awsca`).
- `internal/netprofile` (`pkgname.go`, `grant.go`, `registry.go`, `denied.go`).
- `e2e/network_profile_registry_test.go` and `e2e/registry_test.go`.
- Commits `cdeb1a7f` (grants, credential reload, CodeArtifact), `b6959207` (npm and pip routes), `20a39956` (grants on
  Jobs), `389e42d7` (chart).

## Open questions

- Every supported client must send the pod token: source-IP authentication alone is ruled out by the README's working
  assumption 2. npm and pip can send it, but which client versions do so reliably (including for tarball and wheel
  downloads, not only metadata) must be checked, and the minimum versions recorded in the image contract.
- Should an allowlist have to name transitive dependencies, as in maul, or may the broker resolve a lockfile's closure
  from the pinned tree and grant exactly that?
- Which ecosystem comes next, Maven or crates, and does it need a separate deps Deployment per credentialed registry to
  limit what one compromise exposes?
- Should `packagePolicy: registry` (trust the registry's own curation) be allowed in patchy at all, or only explicit
  allowlists?
