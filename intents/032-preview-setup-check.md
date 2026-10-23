---
id: "032"
slug: preview-setup-check
title: "Set up and verify previews with patchy setup previews and patchy check previews"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 6
area: previews
effort: high
status: proposed
depends_on:
  - "029-preview-gateway"
refs:
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/previewsetup"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/previewdetect"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/previewapply"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/previewcheck"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/setuppreviews.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/checkpreviews.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/set-up-previews.md"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/preview-gateway.md#platform-recipes"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/deploy/terraform/aws"
  - "https://github.com/devthenet-labs/maul/commit/436a9de017d0c1ea9a4eec0e196536874ed659f9"
  - "https://github.com/devthenet-labs/maul/commit/cf62d1b9c4e2a3566d6d51e3e65ce23c26431ca9"
issue: https://github.com/bitwise-media-group/intents/issues/33
---

# [patchy] Set up and verify previews with patchy setup previews and patchy check previews

## What should change, and why?

An operator with a running patchy install runs `patchy setup previews --edge <recipe>` and gets every file previews
need: chart values, cert-manager or tunnel manifests, pinned upstream chart values, 0600 Secret manifests and an ordered
`NEXT-STEPS.md`. With `--apply`, the command also runs the in-cluster steps and undoes them if a step fails.
`patchy check previews` then prints one PASS, WARN, FAIL or SKIP line per check (config, DNS, TLS, OIDC, viewers, nodes,
gateway egress, upstream versions, isolation), so the operator knows the install is safe before any intent uses it. Four
edges are supported: an existing Ingress or Gateway API edge, the gateway's own TLS on a LoadBalancer, a Tailscale
device, and Cloudflare Tunnel.

maul's previews only became usable by other teams once setup and check existed. Before that, every install copied one
team's manual steps. A neutral chart is not enough for provider neutrality: the recipes and the preflight checks must
also work on every platform without a cloud CLI. Several of maul's recipes default to long-lived DNS keys, and its
Cloudflare recipe hands TLS termination to a third party without saying so in the output. This intent fixes both.

Scope:

- Port `previewsetup`, `previewdetect` and `previewapply` into `cmd/patchy/internal/`, wired as `patchy setup previews`
  with `--edge existing|gateway-tls|tailscale|cloudflare-tunnel`, `--platform k3d|k3s|eks|gke|aks|other`, `--detect`
  (read-only, never reads a Secret), `--dry-run` and `--apply` (Secrets, upstream installs, Certificate wait,
  `helm upgrade`, then `check previews`, with undo on failure).
- Write chart values for the 028 and 029 keys only (`preview.*`, `previewGateway.*`). Drop every legacy ALB and
  `previewAuth.stage` output. `forwardedHops` stays fixed per recipe.
- `--edge cloudflare-tunnel` refuses to run without `--accept-edge-tls-termination`, and `NEXT-STEPS.md` and
  `check previews` state that Cloudflare sees preview traffic in clear text.
- DNS-01 for `gateway-tls` and `tailscale`: generate cert-manager solver config that uses workload identity where the
  platform has it (EKS Pod Identity or IRSA for Route 53, GKE Workload Identity for Cloud DNS, Azure Workload Identity
  for Azure DNS). Accept a static key file only with a WARN, both in the output and in `check previews`.
- Viewers are OIDC groups or users (`--viewer-group`, `--viewer-user`), mapped through the 029 claim prefixes, with no
  assumption that they are GitHub teams.
- Keep `answers.yaml` free of secrets, so an operator can commit it to their config repository as the record of the
  preview install. Credentials are read from files or stdin into redacted types and written only into 0600 manifests.
- Port the upstream pins (`previewsetup/pins.go`) with the renovate custom manager and a CI `preview-pins` job that
  checks each pinned chart, CRD set and image digest exists.
- Port `previewcheck` into `patchy check previews -n <namespace>`: `preview-config` (gateway mode, sign-in host outside
  the suffix and on a separate registrable domain), `preview-dns`, `preview-tls`, `preview-oidc`,
  `preview-gateway-host`, `preview-gateway-allowlist`, `preview-viewers`, `preview-nodes` (selector, taint, and the CNI
  agent DaemonSet running on every preview node), `preview-upstreams`, and new `preview-gateway-egress` (the gateway
  NetworkPolicy has no unrestricted rule). `--isolation` runs the ingress and egress probe from 028.
- Cloud modules are pluggable. Write a provider contract in `docs/deployment/preview-providers.md` that says what a
  module must output: registry host and path prefix, node pull identity, a node pool with the preview label and taint,
  DNS zone, certificate or DNS-01 identity, and the gateway edge address. `setup previews` accepts those outputs as a
  values file (`--provider-outputs`).

## How will we know it is done?

- [ ] Golden tests cover the files each recipe writes on each `--platform`. A test asserts `--dry-run` output and
      `answers.yaml` contain no credential bytes.
- [ ] e2e on k3d in CI: `patchy setup previews --edge gateway-tls --apply` with a local CA issuer leads to a signed-in,
      Ready preview of a hand-applied Preview. A failure injected after `helm upgrade` leaves the cluster as it was.
- [ ] `patchy check previews -n patchy` on the k3d install prints only PASS or SKIP. Deleting the slot NetworkPolicy,
      removing the taint from a preview node, unbinding every viewer, or adding a `0.0.0.0/0` egress rule to the gateway
      each turns one named line to FAIL.
- [ ] `patchy setup previews --edge cloudflare-tunnel` without `--accept-edge-tls-termination` exits non-zero with a
      message naming the trade-off.
- [ ] A unit test shows the `gateway-tls` recipe on `--platform eks` with `--dns-identity pod-identity` writes no
      Secret, and with a static key file writes a WARN line in `NEXT-STEPS.md`.
- [ ] The CI `preview-pins` job fails when a pin names a chart version or image digest that does not exist.
- [ ] `docs/deployment/preview-providers.md` exists, and a test validates the sample `--provider-outputs` file against
      the contract's JSON schema.

## Isolation invariants

- **No credentials in agent pods:** the CLI runs outside the cluster with the operator's kubeconfig. Credentials go only
  into 0600 manifests in the release namespace or into workload identity bindings for edge components. None reach a
  slot, agent or broker namespace, and `--detect` never reads a Secret.
- **Broker-only egress:** edge components (cert-manager, cloudflared, the Tailscale operator) run outside slot and agent
  namespaces and get no path into them. `check previews --isolation` proves slots have no egress, and
  `preview-gateway-egress` proves the gateway allowlist stays narrow.
- **Custom resources for state, git for artifacts, GitHub as projection:** install state lives in chart values and
  Kubernetes objects. `answers.yaml` is the operator's committable record of the preview configuration. Neither command
  calls GitHub or any cloud provider API.

## Out of scope

- Creating DNS records, node pools, IdP clients or registries. These stay operator-owned, as in maul.
- Shipping cloud terraform modules in the patchy repository (see open questions).
- Migration from maul's legacy ALB path, which patchy never had.
- The intent-side preview projection (031) and image resolution (030).

## Depends on

- `029-preview-gateway`: the gateway chart keys, Service, OIDC and viewer configuration that the recipes write and the
  checks probe, and through it the 028 slots and isolation probe.

## References

- `cmd/maul/internal/previewsetup/` (`answers.go`, `plan.go`, `nextsteps.go`, `secrets.go`, `gatewaytls.go`,
  `cloudflare.go`, `existing.go`, `pins.go`), `previewdetect/`, `previewapply/` at `devthenet-labs/maul@55b163a8`.
- `cmd/maul/internal/previewcheck/` (`check.go`, `network.go`, `nodes.go`, `viewers.go`, `upstreams.go`,
  `isolation.go`).
- `cmd/maul/internal/cli/setuppreviews.go`, `setuppreviews_apply.go`, `checkpreviews.go`, `checkpreviews_e2e.go`;
  `e2e/preview_setup_test.go`.
- `docs/intents/set-up-previews.md` ("Pick a recipe", "The recipes", "Security");
  `docs/configuration/preview-gateway.md` ("Platform recipes", "Checking it"); `docs/cli/maul_setup_previews.md`.
- `tasks.toml` `[preview-pins]` and `.github/workflows/ci.yaml` (the preview-pins job).
- `deploy/terraform/aws/` and `docs/intents/terraform-module.md`, as input to the provider contract only.
- Commits 436a9de0, 3501967d, f763d0e6, eed05607, 6ffa95e7, cf62d1b9 (setup previews), 0934412b (check previews).

## Open questions

- Should patchy ship an AWS reference module at all? Options: none, only the provider contract; a module in
  `patchy-app-manifests` beside its existing `modules/aws` and `modules/google`; or a separate repository per cloud.
  maul's module also hard-wires GitHub Actions OIDC publisher trust and legacy ALB inputs.
- Is Cloudflare Tunnel acceptable at all for private previews, even with the acknowledgement flag?
- Should `--apply` stay in scope, or should the command only write files for GitOps to apply?
- Which `check previews` lines should also run as a periodic in-cluster probe that exports metrics, as maul's relay does
  for unprotected hosts?
