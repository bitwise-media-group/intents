---
id: "014"
slug: repository-owner-toolkit
title: "Agent base image, example images and patchy init app for application teams"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 2
area: runtime
effort: medium
status: proposed
depends_on:
  - "012-repository-image-pinning"
  - "013-repository-image-execution"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/Dockerfile.agent-base"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/examples/agent-images"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/scaffold"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/cmd/maul/internal/cli/init.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/intents/onboarding-app.md#signing-the-agent-image"
  - "https://github.com/devthenet-labs/maul/commit/bcb2b5578fe5d87801ae834667e223dafe921a32"
issue: https://github.com/bitwise-media-group/intents/issues/15
---

# [patchy] Agent base image, example images and patchy init app for application teams

## What should change, and why?

Once this lands, an application team can produce a compliant, signed agent image without cluster access. They run
`patchy init app --toolchain go --registry ghcr.io/acme/agent-images` in their repository and get `.patchy/agent.yaml`,
a `.patchy/Dockerfile` built `FROM` a digest-pinned patchy agent base image, and a trusted publisher workflow. On every
push to the default branch the publisher builds the image, validates it as data, pushes it to the allowlisted registry
prefix with short-lived OIDC credentials, and cosign-signs the exact digest it validated.
`patchy check image <ref> --run` then proves the image passes source-controller's checks and the in-pod preflight before
the team declares it.

Repository images (`012-repository-image-pinning`, `013-repository-image-execution`) are only usable if owners can build
images that meet the image contract and carry the operator's signature. maul's toolkit does this for ECR only and leaves
signing optional. patchy's toolkit is registry-neutral and signing is mandatory: a publisher with no signing key fails,
because an unsigned image can never be pinned.

Scope:

- Port `Dockerfile.agent-base` (wolfi, glibc, uid 65532, GNU tools, `bash`, `git`, no reserved ENV) and publish it
  multi-arch from patchy's release pipeline as `ghcr.io/bitwise-media-group/patchy/agent-base`, signed with the release
  key. Port `examples/agent-images/{go,node,python}` on top of it, each baking its dependencies.
- Port `cmd/maul/internal/scaffold` and the `init app` command to `cmd/patchy/internal/scaffold` and `patchy init app`.
  Keep `--existing`, `--force` with `KeepToolchain`, `Plan` before `Write`, and printed next steps. Write only the agent
  toolchain and its publisher: `.patchy/agent.yaml` with an immutable `toolchain-v<N>` tag, `.patchy/Dockerfile`,
  `.github/workflows/publish-agent.yml` and `.github/actions/publish/`.
- Add `--toolchain go|node|python`, with templates derived from the examples. Go is ported; node and python are new.
- Make the publisher registry-neutral. `--registry` accepts GHCR, Artifact Registry, ACR or ECR, and the workflow
  authenticates with that registry's OIDC path (`GITHUB_TOKEN` with `packages: write`, Google workload identity
  federation, `azure/login` federated credentials, or an AWS role). No account, role or key id is written into the
  repository; they come from repository variables.
- Make signing mandatory. `AGENT_SIGNING_KEY` takes a cosign KMS URI (`awskms://`, `gcpkms://`, `azurekms://` or
  `hashivault://`). The workflow fails before pushing when it is unset or not a KMS URI. It signs the validated digest
  and verifies the signature with the public key before it reports success.
- Add `--run` to `patchy check image`: run `agent-runner` preflight in a local container shaped like the agent pod (uid
  65532, read-only root, no network, all capabilities dropped, writable `/workspace` and `/tmp` only), with
  `agent-runner` and the CLI copied from the configured runner image.
- Docs: an application onboarding page covering the image contract, the scaffold, registry and OIDC setup per registry,
  signing, and how to hand the public key to the operator for `agent.repositoryImages.cosignPublicKey`.

## How will we know it is done?

- [ ] Scaffold golden tests pass for `--toolchain go`, `node` and `python`, new and `--existing`. `Write` refuses to
      overwrite without `--force`, and `--force` keeps an existing `.patchy/agent.yaml` tag.
- [ ] The scaffolded `guard.test.cjs`, `test_workflows.py` and `test_validate_oci.py` run in patchy CI against every
      golden output and pass.
- [ ] A workflow test shows the scaffolded publisher fails, with a message naming `AGENT_SIGNING_KEY`, when the variable
      is empty or is not a KMS URI, and that no push step runs.
- [ ] Golden outputs for GHCR, Artifact Registry, ACR and ECR each name only that registry's OIDC login action and no
      long-lived secret.
- [ ] `patchy check image <go-example> --run` exits 0. Against an Alpine (musl) image it exits non-zero with
      `image_incompatible`.
- [ ] An e2e scenario builds the Go example, signs it with a test key, and the e2e cluster from
      `013-repository-image-execution` pins and runs it for a remediation.

## Isolation invariants

- **No credentials in agent pods:** nothing here changes the pod. The publisher's registry and KMS credentials are
  short-lived OIDC credentials in the application's CI, scoped to the default branch and the publisher workflow file.
- **Broker-only egress:** the base image and examples bake dependencies in and set offline switches (`GOPROXY=off`,
  `PIP_NO_INDEX=1`, `npm_config_offline=true`), so they work with no egress. When `023-broker-deps-go` lands, the
  controller-owned env replaces those switches; the image does not need to change.
- **Custom resources for state, git for artifacts, GitHub as projection:** the declaration is a file in the
  application's git tree. Intent changesets can never change `.patchy/` or `.github/`, so a toolchain change is always a
  human commit. Signing ties what pods run to the operator-trusted key, not to registry write access.

## Out of scope

- The preview runtime image and its publisher (`publish-runtime.yml`). `030-preview-image-supply` documents the
  publisher contract; scaffolding a runtime publisher is not owned by any intent yet.
- `patchy check project` and the intent Project onboarding flow (`027-intents-operator-onboarding`), which should call
  the same image check per repository.
- Terraform modules for registries, roles and KMS keys. maul's `deploy/terraform/aws` is not ported here.
- Keyless signing, and CI systems other than GitHub Actions.

## Depends on

- `012-repository-image-pinning`: the image contract, the resolver checks that `patchy check image` reuses, and the
  signature forms the publisher must produce.
- `013-repository-image-execution`: `agent-runner` preflight and the pod shape that `--run` reproduces locally.

## References

- `Dockerfile.agent-base` and `examples/agent-images` (with its `README.md`), pinned to `devthenet-labs/maul@55b163a8`.
- `cmd/maul/internal/scaffold` and `cmd/maul/internal/cli/init.go` (`cmd/patchy/...` at `86a3f567^`), including the
  publisher templates under `templates/base/.github/actions/publish`.
- `cmd/maul/internal/cli/check.go` and `cmd/maul/internal/imagecheck` for `--run`.
- `docs/intents/onboarding-app.md`, sections "Scaffold the repository", "Signing the agent image" and "Check the agent
  image before the Project".
- Commits `bcb2b557` (agent base and examples) and `b4c563af` (`check image`).

## Open questions

- Should patchy publish and sign the agent base image itself, or ship only the Dockerfile and let each operator build
  and sign their own base?
- Is node and python scaffolding in scope for this build, or should it ship Go only and add the other toolchains once
  the Go path is proven?
- Which signing key model should the docs recommend: one operator KMS key granted to every application publisher, or one
  key per team with several keys in `cosignPublicKey`?
- Should `patchy init app` refuse to write a publisher for a registry prefix that `patchy check image` reports as
  outside the operator's allowlist, when the operator's allowlist is known?
