---
description: "Isolated, signed-in live previews for every intent pull request."
---

# Previews

Each intent pull request can be deployed to a live URL of its own until it merges. A preview runs agent-written
application code, so it is isolated as carefully as an agent pod: no credentials, no egress and a closed resolver.

maul's previews require EKS Auto Mode and ECR, and carry a legacy ALB path that admits whole subnets. These intents port
the gateway-only path and make it provider-neutral:

- **Slots** (028). Isolated namespaces on dedicated nodes, on any NetworkPolicy-enforcing cluster, with fail-closed
  admission and digest-only images. A hand-written `Preview` becomes a running, isolated app.
- **Gateway** (029). OIDC sign-in, Kubernetes RBAC authorisation, and an enforcing Content-Security-Policy on every
  response so preview code cannot use the viewer's browser as a way out.
- **Images** (030). Tags resolved to digests by a controller, across ECR, GAR, ACR, GHCR and Harbor, with provenance
  archived.
- **Intents** (031). A preview for every open intent pull request, with its lifecycle recorded in git.
- **Setup** (032). `patchy setup previews` recipes for four kinds of edge, and `patchy check previews` with portable
  ingress and egress probes.

Brokered outbound access for previews (for example to staging APIs) is deliberately left as an open question.

--8<-- "build/intent-docs/areas/previews.md"
