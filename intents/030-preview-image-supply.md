---
id: "030"
slug: preview-image-supply
title: "Digest-pinned, registry-neutral preview images with archived build provenance"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 6
area: previews
effort: medium
status: proposed
depends_on:
  - "028-preview-slots"
  - "006-durable-records"
  - "012-repository-image-pinning"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/controller/preview/render.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/preview-admission.yaml"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/_preview.tpl"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnerimage/resolve"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/onboarding-app.md#publishing-the-images"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/deploy/terraform/aws/modules/app/main.tf"
  - "https://github.com/devthenet-labs/maul/commit/e32fd67d0b69d2524df7140f37f262f62d5cad72"
issue: https://github.com/bitwise-media-group/intents/issues/31
---

# [patchy] Digest-pinned, registry-neutral preview images with archived build provenance

## What should change, and why?

An operator, or later the intent-controller, can write a Preview component that names a source revision instead of a
digest. patchy resolves `<prefix><leaf>:sha-<revision>` to an image digest once, in a credentialed controller, records
it in the Preview spec, and runs exactly that digest. A later retag of `sha-<revision>` on a mutable registry cannot
change what runs. If the operator asks for it, an unsigned or wrongly signed image never reaches a slot. Each resolved
image gets a durable record (digest, revision, publisher, signature verdict) written by the 006 records writer. This
works the same against ECR, GAR, ACR, GHCR and Harbor.

maul pins previews by tag (`render.go` `image()` returns `ImageRepository + ":sha-" + Revision`) and relies on ECR's
immutable tags. Its chart accepts any registry, and its runtime publisher never signs. Moving previews to any cloud
without digest pinning would open a supply-chain gap, and the provenance of what was previewed would live only in a CR
status that is deleted with the Preview.

Scope:

- Preview API: `components[].revision` (40-hex) becomes an alternative to `components[].digest`. CEL requires at least
  one, and makes `digest` immutable once set. A component with only `revision` puts the Preview in phase `Resolving`.
  preview-controller renders nothing until every component has a digest.
- New `PreviewImageReconciler` in source-controller, which already resolves and verifies agent images after 012. Reuse
  that resolver package (maul's `internal/runnerimage/resolve`): one HEAD on the tag, then everything by digest,
  platform and size checks on every runnable child of an index, and the index digest recorded. Write `digest` with
  server-side apply under its own field manager, so it never fights the spec's other writer.
- Optional verification: `preview.imageVerification.mode` (`off`, `warn`, `required`) with an operator ECDSA public key
  or a keyless identity (issuer plus subject pattern). On `required`, a failure sets condition `ImageVerified=False`
  with the reason, and no Deployment is created.
- Registry credentials stay controller-tier. Prefer workload identity for the source-controller ServiceAccount (EKS Pod
  Identity or IRSA, GKE Workload Identity, Azure Workload Identity). Accept a docker-config Secret in the release
  namespace (`preview.imageResolver.pullSecret`) for GHCR and Harbor. Never mount it in a slot or agent namespace.
- Node pulls stay pull-only on the preview prefix. Document the node identity for EKS (node role), GKE (node service
  account), AKS (kubelet identity) and k3s (`registries.yaml` on preview nodes only).
- Keep maul's chart rule (commit e32fd67d) that `preview.imageRegistry` plus `preview.imagePathPrefix` is disjoint from
  the agent image allowlist. A render guard fails if the two overlap.
- Provenance record: on first resolution, hand the 006 writer a markdown record with the Preview, component, revision,
  repository, digest, platforms, resolution time, signature verdict and signer identity, and the OCI
  `org.opencontainers.image.source` and `revision` annotations if present. Write it at
  `previews/<preview>/images/<component>-<digest prefix>.md` in the Project's records repository.
- The build path stays external: any CI that pushes `sha-<revision>` under the prefix works. Document the expected
  publisher contract without assuming GitHub Actions or AWS.

## How will we know it is done?

- [ ] envtest: a Preview with `revision` and no `digest` stays `Resolving` with no Deployment; once the reconciler
      writes `digest`, preview-controller renders `<repository>@sha256:<digest>`.
- [ ] envtest: an update that changes a set `digest` is refused by CEL.
- [ ] Integration test with an in-process OCI registry: retagging `sha-<rev>` to a different image after resolution does
      not change the rendered image, and `status.components[].imageID` equals the recorded digest.
- [ ] Integration test: with `imageVerification.mode: required`, an unsigned image gives `ImageVerified=False` and no
      Deployment, and an image signed by the operator key is admitted.
- [ ] e2e with the 005 fake kubelet and the 006 fake records target: each Ready Preview has one provenance record per
      component, and its digest matches the Deployment's image.
- [ ] `helm template` fails when the preview image prefix overlaps an entry in the agent image allowlist.
- [ ] Unit tests in the resolver cover ECR, GAR, ACR, GHCR and Harbor reference forms and their credential sources, with
      no live registry call.

## Isolation invariants

- **No credentials in agent pods:** the registry credential lives only with source-controller, through workload identity
  or a release-namespace Secret. Slot and agent pods never see it. Node credentials are pull-only on the preview prefix.
  The prefix disjointness rule stops a runtime image built from a pull request from ever being admitted as an agent
  image.
- **Broker-only egress:** no change for agent or slot pods. Only source-controller, which is controller-tier, talks to
  the registry.
- **Custom resources for state, git for artifacts, GitHub as projection:** the resolved digest is state in the Preview
  CR. The provenance record is a durable artifact written by the 006 controller-side writer, never by a slot or agent
  pod. No GitHub API is used, and no publisher is assumed.

## Out of scope

- An in-cluster image builder (open question below).
- Scaffolding a runtime image publisher such as maul's `publish-runtime.yml`, or publisher identities. 014 scaffolds
  only the agent image publisher, and 032 writes only edge and chart configuration.
- Writing revisions into Preview specs from intent pull requests (031).
- SBOM generation or vulnerability scanning of preview images.

## Depends on

- `028-preview-slots`: the Preview CRD, preview-controller and the digest-only slot admission policy.
- `006-durable-records`: the controller-side writer and records repository layout for the provenance record.
- `012-repository-image-pinning`: the controller-tier registry resolver and cosign verifier this intent reuses for
  preview images, and the allowlist that must stay disjoint from the preview image prefix.

## References

- `internal/controller/preview/render.go` (`image()` and the component validation near line 215) at
  `devthenet-labs/maul@55b163a8`.
- `charts/maul/templates/preview-admission.yaml` (the image rule built from `maul.previewImagePrefix`) and
  `charts/maul/templates/_preview.tpl`.
- `internal/runnerimage/resolve/doc.go`, `resolver.go` and `signature.go`: pin-once resolution and in-process signature
  verification for agent images, to reuse here.
- `docs/intents/onboarding-app.md` sections "The runtime contract" and "Publishing the images" ("The runtime publisher
  never signs").
- `deploy/terraform/aws/modules/app/main.tf` (`image_tag_mutability = "IMMUTABLE"` and expiry rules).
- Commit e32fd67d (configurable preview image prefix with enforced agent/preview disjointness).

## Open questions

- Should `012-repository-image-pinning` be a declared dependency? This intent reuses its resolver and verifier, and
  would otherwise have to port them itself.
- Who owns `spec.components[].digest`? Server-side apply with a separate field manager is proposed. The alternative is a
  `status.resolved` list that preview-controller reads, which keeps a single spec writer.
- Should patchy add an in-cluster builder that builds from source-controller's pull-request artifact? It removes the
  external CI dependency, but needs relaxed pod security, build nodes, broker-routed dependency fetches and a
  broker-held push credential.
- Where do provenance records live, and how long are they kept, given that maul's module expires `sha-` images after 30
  days while git history is permanent?
