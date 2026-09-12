# Mock Core Banking service

The mock service owns the customer-facing banking data used by the demo. It is
separate from Financial Sensing so the agent can eventually consume customer
context and apply confirmed actions through HTTP instead of reading or writing
the banking database directly.

## Data ownership

Core Banking owns `customers`, `accounts`, `transactions`, `recurring_events`,
`budgets`, `saving_goals`, `reminders`, and request idempotency records.
Financial Sensing continues to own `radar_signals`, `agent_recommendations`, and
`agent_action_logs`.

All data is synthetic. Demo login is not production authentication.

## Run locally

With Python:

```powershell
Set-Location mock-core-banking-service
python main.py
```

With Docker Compose (MySQL 8.4 + Core Banking):

```powershell
docker compose up --build -d mysql corebanking
```

- API: http://localhost:8090
- Swagger: http://localhost:8090/docs
- Health: http://localhost:8090/health

The Core Banking service uses MySQL 8.4 through PyMySQL. The Compose volume
`corebanking-mysql-data` keeps database state across container restarts. Remove
the volume only when an explicit demo reset is wanted.

```dotenv
CORE_BANKING_DATABASE_URL=mysql+pymysql://corebanking:corebanking@mysql:3306/corebanking?charset=utf8mb4
```

The credentials in `docker-compose.yml` are local demo credentials only. Use
secret-managed credentials outside the local demo environment.

## Customer transaction flow

```text
POST transaction
  -> validate account ownership and balance
  -> update account balance
  -> persist transaction
  -> update matching active budget spending
  -> return transaction and current account
```

Write endpoints accept an optional `Idempotency-Key` header. Agent action IDs
should be used as keys so retries return the original response without applying
the action twice.

## Phase boundary

Financial Sensing now uses an HTTP `BankingGateway` for every customer read and
confirmed action. Its own database keeps only signals, recommendations, and
action audit data. For local Compose networking, the agent uses:

```dotenv
CORE_BANKING_BASE_URL=http://corebanking:8090
```

The deployed AgentBase runtime must be configured with a reachable HTTPS Core
Banking URL before this version can be deployed; `localhost` and the Compose
service name are local-only.
