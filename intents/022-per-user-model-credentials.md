---
id: "022"
slug: per-user-model-credentials
title: "Let people pay for their runs with their own model keys, injected only by the broker"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 5
area: broker
effort: high
status: proposed
depends_on:
  - "021-run-attribution-usage"
  - "002-no-credentials-in-agent-pods"
  - "025-intents-dashboard"
refs:
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/configuration/user-credentials.md"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/api/v1alpha1/modelcredential_types.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/usercred.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/credhealth.go"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/broker/credstore"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/credgate"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/web/account.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/charts/maul/templates/user-credentials-policy.yaml"
  - "https://github.com/devthenet-labs/maul/commit/53e3b01abc719b7c9840efd57cc2d9166461a6e1"
issue: https://github.com/bitwise-media-group/intents/issues/23
---

# [patchy] Let people pay for their runs with their own model keys, injected only by the broker

## What should change, and why?

Once this lands, a signed-in person can store their own Anthropic or OpenAI API key on the status page's Account page
and see only its fingerprint and health from then on. Under `enforce`, every run attributed to that person is paid with
their key, which the egress broker attaches on the way out. A run whose person has no valid key is held as `Blocked`
with condition `CredentialRequired` instead of failing on a 403. Revoking a key takes effect within 60 seconds. Runs
with no person behind them (Finding investigations, unattributed remediations) keep the org credential.

Organisations want spend and accountability spread across the people who start runs, without ever putting a credential
in an agent pod. maul's design already does this: keys live in a dedicated namespace, the broker is the only reader, and
the pod carries only its pod-bound identity token. patchy ports it keyed on the verified principal from
`021-run-attribution-usage` rather than a GitHub numeric id, and narrows who can write Secrets.

This is the largest intent here. If it does not fit one build, the planner should split it into two builds: (a) the
store, broker resolution, health probes and run holds, operable by a credentials admin with `kubectl`; then (b) the
Account page and the credential writer. Each half is usable on its own.

Scope:

- API: a `ModelCredential` kind (short name `mcred`, not in the `patchy` category) with immutable `spec.owner` (the
  principal string from `021-run-attribution-usage`), `spec.provider` (`anthropic` or `openai`) and `spec.kind`
  (`api-key`, or `oauth-token` for Anthropic only), and status `fingerprint`, `health`, `secretVersion`, `lastUsedAt`
  and `lastRejectedAt`. Records and Secrets are named from a 16-hex owner hash, so no caller picks a name.
- Store: one Secret per person and provider, `cred-<owner hash>-<provider>`, in a dedicated credentials namespace that
  is neither the release nor the agent namespace. Port the three ValidatingAdmissionPolicies (records, status
  single-writer per field, Secret shape and owner-hash name and label) with `failurePolicy: Fail`.
- Broker: port `internal/broker/usercred.go`, `credstore` and `credhealth.go`. Per request, after TokenReview, read the
  caller pod with a UID check and its `patchy.bitwisemedia.uk/attributed-to` annotation. Under `enforce`, resolve the
  person's record and Secret for the route's provider only, with no fallback to the org key. Use a metadata-only Secret
  informer and a live data read cached for at most one minute. Probe health from the broker itself (`GET /v1/models` for
  an API key, one output token for a setup-token) and write it as conditional status patches. Refusal reasons
  (`credential_missing`, `credential_rejected` and the rest) go into the agent-visible error, the audit line and a
  counter.
- Modes: `egressBroker.userCredentials.mode` is `off`, `attribute` or `enforce`. Keep the subscription guard that
  refuses a setup-token org credential without `orgCredentialIsPersonal: acknowledged`.
- Holds: port `internal/credgate` into remediation-controller and intent-controller. They read only the record by its
  derived name, never a Secret. Holds go to CR conditions (`CredentialMissing`, `CredentialRejected`,
  `CredentialUnverified`) and to the run record, and to GitHub only as a projection. A hold lifts when the key turns
  `Valid`, or on a re-approval through `017-intent-approval` by an approver whose own key is `Valid`.
- Writer: a dedicated `credential-writer` Deployment is the only workload with Secret RBAC in the credentials namespace
  (`create`, `update` and `delete`; never `get`, `list`, `watch` or `patch`). status-server forwards the user's sign-in
  ID token and the key. The writer verifies the token against the OIDC issuer itself and derives the owner, so
  status-server holds no Secret RBAC at all.
- Account page: port `internal/web/account.go` and `AccountView.tsx` onto the dashboard from `025-intents-dashboard`. It
  is write-only: store, replace and delete, as a same-origin JSON POST capped at 8 KiB, behind an access review on the
  virtual `modelcredentials/self` subresource. No response ever contains a key.

## How will we know it is done?

- [ ] Ported unit and property tests (`usercred_test.go`, `usercred_property_test.go`, `credhealth_test.go`) and the
      credstore and admission-policy envtests pass under patchy names.
- [ ] An e2e scenario with fake upstreams under `enforce`: a person with no key has their run `Blocked` with
      `CredentialRequired`. Storing a key on the Account page releases it, and the broker audit line carries that key's
      fingerprint.
- [ ] An e2e scenario deletes the credential Secret mid-run. The next model request fails with `credential_missing`
      within 60 seconds, including when the informer watch is stalled.
- [ ] An e2e scenario shows an unattributed Finding investigation under `enforce` still paid with the org credential.
- [ ] Inspecting every agent pod spec shows no new env, volume or Secret reference. The agent namespace contains no
      credential Secret.
- [ ] An envtest shows that status-server's ServiceAccount cannot `get`, `create` or `patch` Secrets in the credentials
      namespace, and that a write to a name not derived from the caller's owner hash is denied.
- [ ] `helm template` fails for a mode other than `off` when the credentials namespace equals the release or agent
      namespace, when attribution is off, or when the org credential is a setup-token without acknowledgement.

## Isolation invariants

- **No credentials in agent pods:** a person's key goes from browser to status-server to credential-writer to a Secret
  in the credentials namespace. Only the broker reads it, and the broker attaches it outbound exactly as it does the org
  key. Pods carry only the pod-bound projected token. Which key pays is decided from the caller pod's attribution
  annotation, which only run controllers can set, so a prompt-injected agent cannot choose another person's key.
- **Broker-only egress:** nothing new leaves agent pods. Health probes are issued by the broker to the provider of that
  key's own route only, never across providers.
- **Custom resources for state, git for artifacts, GitHub as projection:** records and holds are custom resources. Run
  records and usage reports in git name the paying credential by fingerprint only. Secrets are never written to git,
  blob storage or an issue. A held run's issue comment is rendered from CR status.

## Out of scope

- Per-user Bedrock, Vertex or Foundry identities. Those routes keep the broker's single cloud identity and get
  attribution and usage only.
- ChatGPT-plan or Codex access tokens, and any key for the copilot harness.
- Envelope encryption or an external secret store for stored keys (see open questions).
- The Usage page and `patchy get usage` (`021-run-attribution-usage`).

## Depends on

- `021-run-attribution-usage`: the verified principal model, the `attributed-to` annotation fenced by admission, and the
  broker's UID-checked pod read.
- `002-no-credentials-in-agent-pods`: every harness brokered, so the broker is the single place a key is attached.
- `025-intents-dashboard`: the signed-in status page, its hardened browser envelope and `/api/me`, which the Account
  page builds on.

## References

- `docs/configuration/user-credentials.md`, sections "The store", "What the broker does", "Holding a run", "Who may do
  what", "Admission policies" and "Security notes", pinned to `devthenet-labs/maul@55b163a8`.
- `api/v1alpha1/modelcredential_types.go` and `modelcredential_names.go`.
- `internal/broker/usercred.go`, `internal/broker/credhealth.go`, `internal/broker/credstore`.
- `internal/credgate` and `internal/credgate/kubecred`.
- `internal/web/account.go`, `internal/web/credstore`, and `docs/configuration/status-server.md#account-page`.
- `charts/maul/templates/user-credentials.yaml`, `charts/maul/templates/user-credentials-policy.yaml` and
  `charts/maul/user_credentials_policy_envtest_test.go`.
- `e2e/user_credentials_test.go` and `e2e/user_credentials_openai_test.go`.
- Commits `53e3b01a` (broker resolution), `5a31f0a6` (holds and Account page), `73f8f381` (OpenAI keys).

## Open questions

- Should the `ModelCredential` records live in the credentials namespace beside the Secrets, as proposed for patchy, or
  in the release namespace as in maul, where the run controllers already have read access?
- Is the separate `credential-writer` worth an extra Deployment, given status-server still sees the key in transit? The
  gain is that a compromised status-server can neither read keys nor write one for a person who is not signed in.
- A broker compromise exposes every stored key. Should keys be envelope-encrypted with a KMS key that only the broker
  can unwrap per request, before this ships to a multi-team cluster?
- Which principals can own a key: only OIDC subjects from status-page sign-in, or also Kubernetes users approving via
  the CLI? This follows from the principal model in `021-run-attribution-usage`.
- Should the Usage and Account pages ship together, or does the Account page belong in `026-intent-actions` with the
  other status-page writes?
