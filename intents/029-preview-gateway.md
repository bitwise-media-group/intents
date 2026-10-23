---
id: "029"
slug: preview-gateway
title: "Signed-in, edge-agnostic access to previews through a hardened gateway"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 6
area: previews
effort: high
status: proposed
depends_on:
  - "028-preview-slots"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/previewauth/gateway.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/previewauth/hygiene.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/previewauth/httpapi/gateway_preview.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/previewauth/httpapi/gateway_signin.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/previewauth/adapters/access"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/preview-auth"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/preview-auth.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/preview-auth.md#the-preview-gateway-off-by-default"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/preview-gateway.md#security"
  - "https://github.com/devthenet-labs/maul/commit/25f990daecc7ceda344641a73f383210ba1072dc"
  - "https://github.com/devthenet-labs/maul/commit/026faf039ea5cfb7ba93132716d3007f0faf87c8"
issue: https://github.com/bitwise-media-group/intents/issues/30
---

# [patchy] Signed-in, edge-agnostic access to previews through a hardened gateway

## What should change, and why?

A reviewer opens `https://<label>.<suffix>`, signs in once through the cluster's OIDC provider (Dex by default), and
sees the live preview if Kubernetes RBAC grants them `get` on `projects/previews` for that Preview's Project. A
non-viewer gets 403. Every response from preview code reaches the browser with an enforcing Content-Security-Policy
added by the gateway, so preview JavaScript cannot send a viewer's data to a third-party origin. The gateway is one
Service, `<fullname>-preview-gateway`, that any edge can point at: an Ingress, a Gateway API route, a LoadBalancer or a
tunnel.

Previews are only useful if reviewers can reach them, and a gateway is the provider-neutral way to do it: no ALB OIDC
and no slot Ingress. It is also the one component that sits on the data path of hostile code, so it is treated as
tier-0. maul's gateway proxies correctly but adds no CSP to proxied responses and allows TCP 443 and 6443 to any
destination. This intent ports the gateway and closes both gaps.

Scope:

- New binary `cmd/preview-gateway`, ported from maul's `cmd/preview-auth` in gateway mode only, with
  `internal/previewauth` ported as `internal/previewgateway`: the sign-in host (`/start`, the OIDC callback), sealed
  relay and host sessions, the single-use handoff-code ledger on a Lease, the SubjectAccessReview access adapter, the
  kube view of Previews, pairwise viewer ids, stream revocation, rate limit, metrics and the background host probe.
- Do not port the relay-as-OIDC-provider endpoints (`/authorize`, `/token`, `/userinfo`, discovery), the ALB annotation
  sets or anything keyed on `previewAuth.stage`.
- Keep maul's request and response hygiene, renamed: Host grammar, the reserved `/.patchy/` prefix, origin rules,
  dropping inbound `X-Patchy-*`, `X-Forwarded-*` and gateway cookies, setting `X-Patchy-Viewer` to the pairwise id, and
  `Set-Cookie` filtering. Cookies are `__Host-patchy-pv` and `__Host-patchy-pv-state-<h>`.
- Route only from `status.serving` plus the Preview's UID, slot and host label, never from spec. Upstream is
  `http://<service>.patchy-preview-<slot>.svc:<port>`.
- New: append an enforcing `Content-Security-Policy` header to every proxied response, after the upstream's own headers.
  Default:
  `default-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'; img-src 'self' data:`.
  Operators extend it with `previewGateway.csp.allowedOrigins`. Browsers enforce every CSP header, so an app-supplied
  policy cannot loosen it.
- New: the gateway Pods get their own ServiceAccount and no other duty. Their NetworkPolicy egress is a default-deny
  allowlist: the OIDC issuer (a Service selector or `previewGateway.oidc.egressCIDRs`), the API server CIDR, and the
  slot namespaces' `http` port. There is no `0.0.0.0/0` rule.
- Generic OIDC: `previewGateway.oidc.issuerURL`, `clientID`, `existingSecret`, and claim mapping with required username
  and group prefixes. Dex is the documented default, not a hard dependency.
- Chart: the Deployment (Pods labelled `patchy.bitwisemedia.uk/preview-gateway: "true"`), the Service on port 80 and an
  optional 443 listener with mounted `kubernetes.io/tls` Secrets, the `<fullname>-preview-viewer` ClusterRole, bindings
  from `previewGateway.viewers`, `forwardedHops` (required with any exposure) and `inboundCIDRs`. Offer at most one of
  `ingress`, `httpRoute` or `service.type: LoadBalancer` exposure.
- Prerequisite fix: rename patchy's status-server cookies in `internal/web/auth/cookies.go` (`patchy-auth`,
  `patchy-auth-provider`) to `__Host-` names, because preview hosts can be same-site with the status host.

## How will we know it is done?

- [ ] e2e with `e2e/fakeoidc` and the 005 fake kubelet: an unauthenticated navigation gets a 302 to the sign-in host, a
      bound viewer reaches the preview, an unbound viewer gets 403, and a background fetch without a session gets 401
      with no cookie.
- [ ] e2e: deleting the viewer's RoleBinding cuts off requests and closes an open WebSocket within the review cache plus
      one re-check (about 40 seconds).
- [ ] A seeded property test in `internal/previewgateway` shows every proxied response carries the gateway CSP exactly
      once, whatever CSP, `Set-Cookie` or cache headers the upstream sends.
- [ ] A headless-browser test against a fixture preview shows `fetch()` to an external origin and a form post to an
      external action are both blocked, while same-origin requests work.
- [ ] Chart render guard: the gateway NetworkPolicy has no egress rule without a destination selector or CIDR, and
      `helm template` fails if `previewGateway.enabled` is true and `forwardedHops` is unset with an exposure.
- [ ] Unit tests: a request carrying `X-Patchy-Viewer`, `X_Forwarded_For` or a `__Host-patchy-pv` cookie reaches the
      upstream without them, and a request for `/.patchy/anything` is never forwarded.
- [ ] Unit test: status-server sets only `__Host-` prefixed cookies.
- [ ] On k3d, a probe Pod in the release namespace without the gateway label cannot reach a slot, and a gateway Pod
      cannot open a connection to an internet address (both from the 028 probe).

## Isolation invariants

- **No credentials in agent pods:** the gateway is controller-tier. It mounts the OIDC client secret, signing keys and
  the pairwise key, and admission keeps it out of slot namespaces. Slot pods still hold nothing. Preview code learns
  only an opaque pairwise id per viewer and Preview.
- **Broker-only egress:** agent pods are untouched. Slot pods still cannot open connections. The gateway's own egress is
  narrowed to the issuer, the API server and slot ports, and the CSP fences browser-side egress from preview code.
- **Custom resources for state, git for artifacts, GitHub as projection:** routing state is the Preview CR's
  `status.serving`. Authorization is Kubernetes RBAC, not GitHub team membership. Sessions are sealed cookies, so there
  is no new store. Nothing reads or writes GitHub.

## Out of scope

- ALB `authenticate-oidc`, relay-as-OIDC-provider endpoints, and permit and require staging.
- Edge recipes, TLS issuance and `patchy setup previews` or the full `patchy check previews` (032).
- Per-Project viewer management in the status page, and any viewer identity besides OIDC.

## Depends on

- `028-preview-slots`: the Preview CRD with `status.serving`, slot namespaces whose NetworkPolicy admits only Pods with
  the gateway label, and the isolation probe.

## References

- `internal/previewauth/gateway.go`, `hygiene.go`, `pairwise.go`, `binding.go` at `devthenet-labs/maul@55b163a8`.
- `internal/previewauth/httpapi/gateway.go`, `gateway_preview.go` (`newProxy`, whose `ModifyResponse` sets no CSP),
  `gateway_signin.go`, `streams.go`, `ratelimit.go`.
- `internal/previewauth/adapters/access`, `dex`, `kubeview`, `keydir`, `tlsdir`, `hostprobe`, `ledger`, and
  `internal/previewauth/fakedex`.
- `cmd/preview-auth/serve.go`, `charts/maul/templates/preview-auth.yaml` (egress rules around line 584),
  `charts/maul/templates/_preview-auth.tpl`.
- `e2e/preview_gateway_test.go`, `e2e/preview_gateway_mode_test.go`.
- `docs/configuration/preview-auth.md` sections "Who may view", "Cookies" and "The preview gateway (off by default)";
  `docs/configuration/preview-gateway.md#security`.
- Commits 25f990da (gateway sign-in and proxy), 026faf03 (gateway end to end), eb0fe5a0 (gateway-mode defaults).
- Pre-rename names (`__Host-patchy-pv`, `/.patchy/`) at `86a3f567^:internal/previewauth/gateway.go`.

## Open questions

- Is the default CSP strict enough without breaking common dev servers? Hot-reload WebSockets need `connect-src 'self'`
  to cover `wss:` on the same host. Confirm on the target browsers, or add it explicitly.
- Should the gateway accept any OIDC issuer directly, or stay Dex-first? Viewer groups today assume GitHub teams through
  Dex's connector.
- Should the gateway run as its own release-namespace Deployment, or in a separate namespace with its own PSA and
  NetworkPolicy defaults, to make the tier-0 boundary clearer?
- Is a separate registrable domain for preview hosts required, or only recommended? Same-site previews weaken `SameSite`
  protections for every other app on that domain.
