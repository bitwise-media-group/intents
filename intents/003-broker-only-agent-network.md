---
id: "003"
slug: broker-only-agent-network
title: "Lock agent pods to broker-only egress and prove it from inside every pod"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: 0
area: runtime
effort: medium
status: proposed
depends_on:
  - "002-no-credentials-in-agent-pods"
refs:
  - "https://github.com/devthenet-labs/maul/commit/28a7657d7b6cf170e0b8ca640875154bcc6f17a3"
  - "https://github.com/devthenet-labs/maul/commit/cf7b5c7ae7a5ebd57519b43b0179f84889835209"
  - "https://github.com/devthenet-labs/maul/tree/55b163a8e8df527e78b9397d1364d385c36d9231/internal/sandboxprobe"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/jobs/dns.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/internal/runnerguard/breaker.go"
  - "https://github.com/devthenet-labs/maul/blob/55b163a8e8df527e78b9397d1364d385c36d9231/docs/deployment/isolation.md#closing-dns"
issue: https://github.com/bitwise-media-group/intents/issues/4
---

# [patchy] Lock agent pods to broker-only egress and prove it from inside every pod

## What should change, and why?

After this lands, a default patchy install renders agent NetworkPolicies whose only egress destinations are the egress
broker Service and the source-controller artifact server. There is no TCP 443 rule and no cluster DNS. Agent pods run
with `dnsPolicy: None`, nameserver `127.0.0.1`, and `hostAliases` for the broker and the artifact server. Before the
agent starts, every agent Job's trusted `prepare` init runs `agent-runner sandbox-probe`. It checks that a public
address, the Kubernetes API and the instance metadata endpoint are all unreachable. A pod that can reach any of them
fails as `SandboxUnenforced`, without using up an attempt, and trips a breaker that stops new agent Jobs. An operator
gets a check on every pod, not an assumption about the CNI.

Today `patchy.broadEgress` in `charts/patchy/templates/_helpers.tpl` keeps "TCP 443 to anywhere" under modes `none` and
`istio`, and the base policy allows DNS to kube-system. DNS through the cluster resolver is a working exfiltration
channel. Whether a NetworkPolicy is enforced at all depends on the CNI: EKS Auto Mode does not enforce one by default,
and policies attach late. Once `002-no-credentials-in-agent-pods` lands, every runner is brokered and no agent pod needs
443 or DNS. This intent makes that working assumption 2 in the chart. It is required before untrusted repository images
(013), dependency routes (023) and previews (028).

Scope:

- Chart egress: the agent egress policy names only the broker pods and the artifact server pods, by namespace and pod
  selector, on their ports. `agent.networkPolicy.broadEgress` accepts only `never`. `auto` and `always` fail the render
  with an explanation. The per-runner `hosts` and `dnsPatterns`, and the agent-side Cilium FQDN, GKE FQDN and Istio
  ServiceEntry rules for model hosts, are removed. The broker's own egress policy is unchanged. The kustomize base and
  the `cilium`, `gke-fqdn` and `istio` components are changed to match.
- DNS: port `internal/jobs/dns.go` and make `agent.networkPolicy.dns: none` the default and only supported value. Pods
  get `dnsPolicy: None`, a loopback nameserver, and `hostAliases` for the broker and artifact server names. The job
  controllers resolve those names when they create a Job (`Config.Resolver`). `ErrUnresolved` fails creation retryably.
  Runners that report `NeedsResolver` are refused. The DNS rule to kube-system is removed from agent policies.
- Probe: port `internal/sandboxprobe` (wait and strict modes, injectable dialer and clock, `DefaultTargets`) and the
  stdlib-only `agent-runner sandbox-probe` subcommand. Every default-image `prepare` script ends with the probe in wait
  mode: it waits a bounded time for the policy to attach, then gives its verdict.
- Probe policy: chart value `agent.sandboxProbe.onUnenforced` takes `fail` (default) or `warn`. This changes maul, where
  a default-image wait probe can never fail the Job. Strict mode is used by repository-image Jobs in
  `013-repository-image-execution`.
- Collectors: investigation, remediation and evaluation collectors map exit 78 to a `SandboxUnenforced` condition on the
  run CR and do not count it as an attempt.
- Breaker: port `internal/runnerguard/breaker.go` with gauge `patchy.sandbox.breaker`. A `SandboxUnenforced` run trips
  it. Until the controller restarts, its scheduler grants no new agent Job slots. This differs from maul, where the
  breaker only stops repository images. 013 adds that fallback.
- Docs: rewrite the network egress section of `docs/deployment/isolation.md` around the broker-only floor, add "Closing
  DNS", and make `NOTES.txt` state the posture.

## How will we know it is done?

- [ ] A chart render test with default values finds that every policy selecting agent-namespace pods allows egress only
      to the broker and artifact server. It finds no port 443 rule, no `ipBlock` egress and no port 53 rule.
- [ ] `helm template` with `broadEgress: auto`, `broadEgress: always` or `dns: cluster` fails with a message naming the
      value.
- [ ] Golden Job YAML for investigation, remediation and evaluation shows `dnsPolicy: None`, nameservers `[127.0.0.1]`,
      `hostAliases` for the broker and artifact server, and the wait probe at the end of `prepare`.
- [ ] `sandboxprobe` unit tests with a fake dialer cover retries, confirmations and the attach wait. The probe exits 78
      when any target is reachable in either mode.
- [ ] An envtest controller test: a Job whose `prepare` init exits 78 sets `SandboxUnenforced` and leaves the attempt
      count unchanged. The breaker trips, `patchy.sandbox.breaker` reads 1 and no new Job is created.
- [ ] A CI job (`hack/sandbox-kind.sh`) on kind with Calico: a canary agent Job passes the probe,
      `getent hosts     example.com` fails inside the agent container, and a request to the broker succeeds. With policy
      enforcement off, the same canary ends `SandboxUnenforced`.
- [ ] A remediation still completes end to end under the new defaults. This uses the kind job, or the
      `005-e2e-agent-pods` harness if it has landed.

## Isolation invariants

- **No credentials in agent pods:** adds none. The probe needs no credential, `automountServiceAccountToken` stays
  false, and `hostAliases` hold only Service names and addresses.
- **Broker-only egress:** this intent makes it structural. The agent policy names only the broker and the read-only
  artifact server, which serves digest-verified tarballs and proxies nothing. No resolver means no DNS channel. The
  probe proves both from inside each pod before the agent runs. The render fails on any posture that reopens 443 or DNS.
- **Custom resources for state, git for artifacts, GitHub as projection:** `SandboxUnenforced` is a condition on the run
  CR. The breaker state is in memory and exposed as a metric. Nothing new is written to GitHub.

## Out of scope

- Strict-mode wiring for repository images and the image fallback after a breaker trip (013).
- Broker TLS or mesh mTLS between agent pods and the broker.
- Dependency fetching through the broker (023, 024) and preview slot DNS (028).
- Cilium `toFQDNs` policies for agents. Agents no longer reach any FQDN.

## Depends on

- `002-no-credentials-in-agent-pods`: every enabled runner is brokered, so no agent pod needs TCP 443 or a resolver.

## References

- `devthenet-labs/maul@55b163a8`: commits 28a7657d (no resolver under `--agent-dns none`) and cf7b5c7a (hold
  default-image agents until the pod's policy attaches).
- `internal/sandboxprobe` (`probe.go`, `wait.go`, `exit.go`), `internal/jobs/dns.go`, `internal/jobs/jobs.go`
  (`waitProbeScript`), `internal/runnerguard/breaker.go`.
- `charts/maul/templates/networkpolicy.yaml`, `charts/maul/templates/networkpolicy-cilium.yaml`,
  `deploy/kustomize/components/agent-dns-none`.
- `docs/deployment/isolation.md`, sections "Network egress — the floor and the fence", "Closing DNS" and "What the agent
  policy does not stop".
- `e2e/intent_dns_test.go`.

## Open questions

- Should the default be `onUnenforced: fail` on every cluster? This intent says yes. A cluster whose CNI does not
  enforce NetworkPolicy then runs no agents until it is fixed.
- Broker TLS: the caller token crosses the cluster network in plaintext HTTP. It is bound to a pod and an audience,
  which is acceptable for model routes. Must broker TLS land before `023-broker-deps-go`, whose tokens may sit in
  package-manager config?
- A DNS allow policy managed outside the chart (an operator's own `allow-dns`) would keep the channel open, and the
  chart cannot see it. Should `patchy check` look for one?
- Is a kind job with Calico affordable in CI on every pull request, or only on changes to `internal/jobs`,
  `internal/sandboxprobe` and the chart's policy templates?
