---
id: "028"
slug: preview-slots
title: "Isolated preview slots and a preview-controller on any NetworkPolicy-enforcing cluster"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 6
area: previews
effort: high
status: proposed
depends_on:
  - "003-broker-only-agent-network"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/preview_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/preview_components.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/preview_routing.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/preview"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/preview-controller"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/preview-foundation.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/preview-admission.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/_preview.tpl"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/hack/preview-isolation-probe"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/previewcheck/isolation.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/preview-controller.md#node-isolation"
  - "https://github.com/devthenet-labs/maul/commit/7b215125ff834ac81b148912fbd0cdc7de5cf6c0"
  - "https://github.com/devthenet-labs/maul/commit/662dc9f2c7468d95abcd193ec999a112d654f4ea"
  - "https://github.com/devthenet-labs/maul/commit/8bca0d3fc7946df9721ebd5867fc0b59b0504c92"
issue: https://github.com/bitwise-media-group/intents/issues/29
---

# [patchy] Isolated preview slots and a preview-controller on any NetworkPolicy-enforcing cluster

## What should change, and why?

An operator turns on `preview.enabled` on any cluster whose CNI enforces NetworkPolicy (k3d, EKS, GKE, AKS) and gets a
fixed pool of chart-created slot namespaces that run untrusted, agent-written application code safely. Applying a
hand-written `Preview` custom resource with a digest-pinned image produces a running, isolated app: a Ready Deployment
and ClusterIP Service per component, and a `status.serving` snapshot that a router can use.
`patchy check previews --isolation` then proves from inside the cluster that a slot can neither be reached by anything
but the future preview gateway nor reach anything itself.

This is the security floor that every later preview intent stands on, and patchy has none of it today. maul built it,
but about a third of maul's preview code is an EKS-only legacy ALB path that admits whole subnets into slots. This
intent ports the gateway-only shape and closes two gaps maul left open: DNS from slots and the cluster-wide outside-slot
policy that blocks CNI agents on non-EKS clusters.

Scope:

- `Preview` CRD under `patchy.bitwisemedia.uk/v1alpha1`, ported from maul's `api/v1alpha1/preview_*.go`: spec `project`,
  optional `intentRef`, immutable `hostLabel`, `ttl` (1h to 72h) and up to four `components` (`name`, `imageRepository`,
  `digest`, `port`, `readinessPath`, `path`); status `phase`, `slot`, `components[].imageID` and `serving`. Keep
  `DesiredPreviewComponents`, `PreviewRoute`, `PreviewPathMatches` and `PreviewComponentServiceName` as pure shared
  helpers. Replace maul's `revision` plus `sha-<40hex>` tag with a required `digest` (`sha256:<64hex>`); 030 adds tag
  resolution, so until then operators write digests by hand.
- `cmd/preview-controller` and `internal/controller/preview`: slot queue, render, rollout and retry, readiness and
  imageID gating, TTL expiry, finalizer cleanup by UID label, orphan sweep and Prometheus metrics. Do not port
  `auth.go`, `sweep_auth`, slot Ingress rendering, the placeholder Ingress or EKS target-health gates. Drop the Ingress
  verbs from the slot Roles. A Preview without `intentRef` is validated by CEL and admission only; the re-derivation
  against an Intent arrives with 031.
- Rendered workloads: one container, `runAsNonRoot`, read-only root filesystem, drop ALL, no env, no envFrom,
  `automountServiceAccountToken: false`, emptyDir only, `image: <repository>@<digest>`, and `dnsPolicy: None` with a
  loopback-only nameserver so the pod has no resolver.
- Chart (`charts/patchy`): slot namespaces `patchy-preview-<n>` (`preview.slotCount`, 1 to 4) with PSA `restricted`, a
  NetworkPolicy with no egress rules at all and ingress only from Pods labelled
  `patchy.bitwisemedia.uk/preview-gateway`, ResourceQuota (0 LoadBalancers, 0 NodePorts) and LimitRange. All are kept on
  uninstall and rollback.
- Fail-closed ValidatingAdmissionPolicies on slot Pods, Deployments and Services: image under
  `preview.imageRegistry`/`preview.imagePathPrefix` in `@sha256:` form, single container, no init or ephemeral
  containers, no Secret env refs, emptyDir only, no host namespaces, `dnsPolicy: None` with the loopback nameserver, the
  node selector plus the exact NoExecute toleration, and no `nodeName` or custom scheduler.
- Outside-slot policy, fixed: forbid the preview toleration and tolerate-all outside slots, except for Pods owned by a
  DaemonSet in an operator-listed set (`preview.nodeIsolation.daemonSetExemptions`, namespace plus DaemonSet name), so
  CNI and node agents can run on preview nodes.
- Generic node isolation: `preview.nodeIsolation.selector`, `taintKey` and `mode` (`required` or an explicit `none`).
  Document node-pool recipes for k3d, EKS, GKE and AKS. Do not render cloud node pools from the chart.
- `patchy check previews --isolation` in `cmd/patchy`: short-lived probe Pods running maul's netprobe, ported here as a
  thin command over the `internal/sandboxprobe` package from 003. It checks ingress (agent namespace, release namespace
  without the gateway label, sibling slot) and egress (an internet address, 169.254.169.254, the API server, the egress
  broker, every controller Service, a sibling slot, a sibling component). It needs no cloud CLI, registry or forge.

## How will we know it is done?

- [ ] envtest against the rendered chart: the VAPs refuse a slot Pod with an image outside the prefix, a tag instead of
      a digest, a Secret env ref, a projected or secret volume, `hostNetwork`, `dnsPolicy: ClusterFirst`, a missing
      toleration or a `nodeName`, and admit the controller's own rendering.
- [ ] envtest: a tolerate-all Pod owned by a listed DaemonSet in `kube-system` is admitted, and the same Pod owned by an
      unlisted DaemonSet or a Deployment is refused.
- [ ] e2e with the 005 fake kubelet: a hand-applied Preview reaches `Ready` with `status.serving` set; deleting it
      empties the slot; TTL expiry moves it to `Expired` and frees the slot for a queued Preview.
- [ ] A k3d CI job runs one test image each for Node, Django, Rails and Go with `dnsPolicy: None`, and each one passes
      its readiness probe. A failure is recorded, not hidden by a fallback resolver.
- [ ] `patchy check previews --isolation` on k3d prints PASS for every ingress and egress line, and prints FAIL on the
      egress line for the internet address after the slot NetworkPolicy is deleted (negative test in the same job).
- [ ] `helm template` fails when `preview.enabled` is true without a node selector and taint key, unless
      `preview.nodeIsolation.mode` is `none`. Golden render fixtures under `hack/testdata/chart-render` contain no
      Ingress and no ALB annotations.
- [ ] An imports test fails if `internal/controller/preview` imports a forge, registry or cloud SDK package.

## Isolation invariants

- **No credentials in agent pods:** slot pods are held to a stricter rule than agent pods. They have no env, no
  ServiceAccount token, no Secret refs and emptyDir volumes only, all enforced by admission. preview-controller talks
  only to the Kubernetes API through namespaced Roles and never reads a Secret. Node pull credentials stay on preview
  nodes, pull-only on the preview prefix.
- **Broker-only egress:** slots get no egress at all, not even to the broker, and no resolver. The probe proves this
  from inside a slot. This intent changes nothing for agent pods, and the slot prefix stays disjoint from the agent
  image allowlist.
- **Custom resources for state, git for artifacts, GitHub as projection:** all preview state is in the `Preview` CR.
  Nothing reads or writes GitHub. Durable preview records arrive with 030 and 031.

## Out of scope

- maul's legacy ALB path: slot Ingresses, the `alb-preview` IngressClassParams, the placeholder Ingress, permit and
  require staging, the unauthenticated-Ingress sweeper and target-health readiness gates.
- Viewer sign-in and any HTTP exposure of slots (029).
- Tag-to-digest resolution and signature checks (030).
- Writing Preview specs from intents (031), and any outbound access from slots, including brokered staging calls.
- Rendering EKS NodeClass or NodePool objects, or any other cloud node pool.

## Depends on

- `003-broker-only-agent-network`: the `internal/sandboxprobe` package (dialer, default targets, verdicts) that the slot
  probe builds on, the loopback-resolver pattern, and the broker and artifact-server addressing the egress probe
  targets.

## References

- `api/v1alpha1/preview_types.go`, `preview_components.go`, `preview_routing.go` at `devthenet-labs/maul@55b163a8`.
- `internal/controller/preview/` (`controller.go`, `render.go`, `workload.go`, `sweep.go`, `isolation.go`) and
  `cmd/preview-controller/`.
- `charts/maul/templates/preview-foundation.yaml`, `preview-admission.yaml`, `preview-nodes.yaml`, `_preview.tpl`, and
  the tests `charts/maul/preview_policy_envtest_test.go`, `preview_policy_isolation_envtest_test.go`,
  `preview_isolation_render_test.go`, `preview_probe_envtest_test.go`.
- `hack/preview-isolation-probe/ingress.sh` and `hack/preview-isolation-probe/cmd/netprobe/`.
- `cmd/maul/internal/previewcheck/isolation.go`, `isolation_policy.go`, `isolation_run.go`.
- `docs/configuration/preview-controller.md` sections "Node isolation", "The serving snapshot" and "Without the legacy
  Ingress"; `docs/deployment/isolation.md#closing-dns` for the loopback-resolver pattern.
- Commits 7b215125 (slot foundation), 71461b8b (isolated nodes), 41331520 (slot renderer), 662dc9f2 (serving snapshot
  and generic node isolation), 8bca0d3f (portable foundation), 0934412b (`check previews --isolation`).
- Pre-rename names (`patchy-preview-<n>`, `charts/patchy/templates/preview-*.yaml`) at `86a3f567^`.

## Open questions

- Does `dnsPolicy: None` break any common framework at startup? If one fails, is a sinkhole CoreDNS that answers only
  `localhost` acceptable, or do we refuse that framework?
- What exactly may an exempt DaemonSet be? Namespace plus name is proposed. Is owner kind DaemonSet enough on GKE
  Dataplane V2, AKS and Cilium? The CNI agent must run on preview nodes, or slot NetworkPolicy is not enforced.
- Is a slot pool of 1 to 4 per release (quota 8 pods, 2 CPU, 2Gi) the right default, or should slot count become a
  per-Project setting?
- Should `nodeIsolation.mode: none` be refused outright when `preview.enabled` is true in a production install, rather
  than documented as unsupported?
