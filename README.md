# MSB Financial Radar

**Cố vấn Tài chính Đón đầu** is a proactive financial agent built around
`PREDICT → ADVISE → ACT`. It detects signals, forecasts risks, produces grounded
recommendations, prepares actions, enforces confirmation, executes business
tools, and records outcomes.

This is not a `FastAPI → LLM → text` wrapper. The MVP has typed state,
orchestration, a deterministic Financial Engine, tools, policy, confirmation,
execution, signal persistence, and action/tool-call tracing.

## Architecture

```mermaid
flowchart LR
  Client[Swagger / API] --> API[FastAPI]
  API --> Runtime[AgentRuntime]
  Runtime --> State[Typed RadarState]
  Runtime --> Registry[Tool Registry]
  Registry --> Engine[Deterministic Financial Engine]
  Registry --> DB[(SQLite / PostgreSQL)]
  Runtime --> Policy[Policy + Confirmation]
  Policy --> Actions[Action Executor]
  Runtime -. grounded context .-> LLM[LLMClient]
  LLM -. Pydantic output .-> Runtime
  Runtime --> Trace[(Signals + Action Logs)]
```

The lifecycle is:

```text
INIT → CONTEXT_READY → SIGNAL_DETECTED → ANALYSIS_READY
     → RECOMMENDATION_READY → ACTION_PREPARED
     → WAITING_CONFIRMATION → EXECUTING → EXECUTED → MONITORING
```

Informational flows may finish at `RECOMMENDATION_READY`. Invalid transitions,
including confirmation bypass, are rejected.

## Financial Engine versus LLM

The Financial Engine is the source of truth for anomaly percentages, recurring
dates, cashflow forecasts, goal gaps, scenario amounts, and budget guardrails.
It accepts an explicit `as_of` date and never imports an LLM.

The LLM may explain supplied evidence and select from valid options. It cannot
query the database, override policy, calculate financial metrics, or claim tool
success. `MockLLMClient` is used locally and in tests.

## Project structure

```text
app/
  main.py                 FastAPI endpoints
  config.py               Environment-backed settings
  database.py             SQLAlchemy setup
  models.py               ORM models and enums
  financial_engine/       Spending, recurring, cashflow, goal calculations
  tools/                  Contracts, JSON schemas, implementations, registry
  policy.py               Risk and confirmation decisions
  llm/                    LLMClient, MockLLMClient, system prompt
  agent/                  Typed state, AgentRuntime, LocalAgentRuntime
  seed/                   Deterministic C001-C004 data and reset command
tests/                    Engine, policy, runtime, confirmation and API tests
main.py                   Port-8080 container entrypoint
Dockerfile                AgentBase-compatible HTTP container
```

## Database

The schema contains `customers`, `accounts`, `transactions`, `recurring_events`,
`saving_goals`, `budgets`, `reminders`, `radar_signals`, and
`agent_recommendations`, and `agent_action_logs`. Recommendations store only the
structured candidate plan and display/audit decision (never hidden chain-of-thought),
expire after 15 minutes by default, and link signals to actions. Action logs include
`recommendation_id`, tool input/output, policy, confirmation, status, and latency.

SQLite is the default. PostgreSQL can be selected through:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@host/database
```

For the Hackathon AgentBase deployment, SQLite is intentionally accepted as
temporary demo persistence with exactly one replica. The image excludes the
database file; initialize C001-C004 explicitly using
`python -m app.seed.reset_demo`. Container or runtime-version replacement loses
container-local SQLite state, so this configuration is not production-safe.

## Setup, seed, and start

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m app.seed.reset_demo
python main.py
```

Swagger is at `http://localhost:8080/docs`; health is at
`http://localhost:8080/health`.

Reset the deterministic demo at any time:

```powershell
python -m app.seed.reset_demo
```

- `C001`: cashflow risk—25m income, 9m balance, 3m safe balance, upcoming 6m
  rent, and historical discretionary spending.
- `C002`: FOOD spending 5m versus a three-month 4m baseline (+25%).
- `C003`: 100m/12-month goal with 22m progress around month four.
- `C004`: upcoming 8m rent against 7.2m balance, demonstrating
  `UPCOMING_RECURRING → CASHFLOW_RISK`.

## C001 hero demo

```json
POST /api/agent/run
{
  "customer_id": "C001",
  "message": "Tài chính tháng này của tôi thế nào?",
  "as_of": "2026-09-01"
}
```

The response contains `recommendation_id`. Select the immutable stored option
without resending tool parameters:

```json
POST /api/agent/select
{"recommendation_id":"<returned-recommendation-id>","option_id":"A"}
```

The response is `WAITING_CONFIRMATION`; Financial Engine and MaaS are not rerun,
and no budget exists yet. Confirm:

```json
POST /api/agent/confirm
{"action_id":"<returned-action-id>","confirmed":true}
```

The resulting state is `MONITORING`, backed by actual tool output; this phase
records monitoring intent but does not start background jobs. For seeded
inputs, the forecast to 2026-09-15 is 1,366,667 VND, calculated from database
evidence rather than embedded as an output constant.

## MVP API

- `GET /api/customers/{customer_id}/snapshot`
- `GET /api/customers/{customer_id}/radar`
- `POST /api/tools/forecast-cashflow`
- `POST /api/tools/detect-spending-anomaly`
- `POST /api/tools/detect-recurring`
- `POST /api/tools/simulate-goal`
- `POST /api/actions/create-budget`
- `POST /api/actions/create-reminder`
- `POST /api/actions/update-goal`
- `POST /api/agent/run`
- `POST /api/agent/select`
- `POST /api/agent/confirm`
- `GET /api/agent/actions/{action_id}`
- `GET /api/customers/{customer_id}/signals`

Direct action endpoints use the same policy path. `create_budget` and
`update_goal` cannot execute before confirmation.

## Tests

```powershell
python -m pytest -vv
```

Tests require no real LLM and cover the engine, cross-signals, tool validation,
policy, transition safety, tracing, confirmation, persistence, and FastAPI E2E.

## LLM configuration

```dotenv
AGENT_RUNTIME=local
LLM_PROVIDER=greennode
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=60
AGENT_RECOMMENDATION_TTL_SECONDS=900
```

`AGENT_RUNTIME=local` uses `MockLLMClient`. `AGENT_RUNTIME=greennode` fails fast
unless `LLM_PROVIDER=greennode` and all MaaS variables are configured, then uses
`GreenNodeLLMClient` against the OpenAI-compatible Chat Completions endpoint.
Installed GreenNode documentation does not guarantee `response_format=json_object`,
so the client uses strict JSON instructions followed by `json.loads`, Pydantic
validation, and bounded retries.

Business logic creates a fixed `CandidateActionPlan` first. MaaS may only return
the narrative summary, reasoning, and an existing `recommended_option_id`; the
server merges that decision with the original immutable action parameters.

## GreenNode AgentBase

The runtime factory supports both `LocalAgentRuntime` and
`GreenNodeAgentRuntime`. The latter is the Custom Agent container implementation:
AgentBase supplies hosting, lifecycle, IAM injection, endpoint, and platform-level
monitoring. The MSB application still owns the orchestration state machine,
Financial Engine, tools, policy/confirmation, persistence, and MaaS calls. Platform
IAM credentials are used by deployment skills/control-plane operations and are not
required for the FastAPI process to boot. Port 8080 and `GET /health` satisfy the
platform contract.

See [AgentBase deployment readiness](docs/AGENTBASE_DEPLOYMENT.md) for the
resource plan, remaining deployment choices, and cost considerations.

Secrets must stay in environment variables or AgentBase Identity and must never
be committed.
