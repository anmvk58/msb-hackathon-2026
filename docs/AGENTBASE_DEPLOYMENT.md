# AgentBase deployment readiness

MSB Financial Radar targets a **Custom Agent** runtime. It keeps its deterministic
Financial Engine and ToolRegistry inside the container; a Resource Gateway is not
needed for this MVP. The tools can later move behind an MCP Resource Gateway when
multiple agents or network-isolated capabilities need to share them.

## Authentication separation

- `GREENNODE_CLIENT_ID` and `GREENNODE_CLIENT_SECRET`: AgentBase platform IAM
  lifecycle authentication. AgentBase injects runtime-specific values after deploy.
- `LLM_API_KEY`: GreenNode MaaS model authentication only.

These credentials are never exchanged or logged as substitutes for each other.

## Runtime contract

- Image platform: `linux/amd64` is the recommended target.
- Container port: `8080`.
- Readiness endpoint: `GET /health` returns HTTP 200.
- Business invocation: `POST /api/agent/run`.
- Runtime mode: `AGENT_RUNTIME=greennode`.

## Resources a deployment would create or consume

No platform resource has been created yet. After explicit approval, the planned
Custom Agent pipeline would involve:

1. One Docker image artifact in the user-selected registry.
2. One AgentBase Custom Agent runtime (`/agent-runtimes`).
3. One automatically created `DEFAULT` runtime endpoint.
4. One platform-managed runtime IAM service account and Agent Identity, injected
   into the container automatically.
5. Existing GreenNode MaaS model/API-key access; no new MaaS key is required if an
   existing active key is selected.

AgentBase managed Container Registry is recommended. Its repository is
pre-provisioned, so deployment would not create another repository. No Memory,
Resource Gateway, Policy Group, outbound-auth provider, VPC, or OpenClaw resource
is planned for this MVP.

## Choices required before an exact deploy command

The deployment skill requires the user to explicitly choose:

- AgentBase managed CR or an external registry.
- Runtime name.
- Environment file path (without platform auto-injected IAM variables).
- POC wallet or real wallet, subject to eligibility.
- PUBLIC or VPC network mode.
- Eligible compute flavor.
- Autoscaling min/max replicas and CPU/memory thresholds.
- Build platform and image tag.

## Cost impact

Deployment may consume billable resources:

- AgentBase runtime compute according to wallet, flavor, replicas, and duration.
- GreenNode MaaS usage according to model/token consumption.
- Container registry storage and transfer under the account's applicable plan.

Exact pricing is account/contract dependent. Check the GreenNode billing console
before choosing the real wallet. If POC eligibility is available, the user must
explicitly choose whether to use it; the deployment process cannot auto-select it.
