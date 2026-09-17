# ChamaCore Production Runbook

This runbook covers deploying and operating ChamaCore as a single FastAPI
service. ChamaCore is a **modular monolith** (ADR-001): one process, one
database, an in-process rate limiter, and an in-process metrics registry.

## Architecture notes that matter in production

- **Single process today.** Rate limiters (`app/core/ratelimit.py`) and
  metrics (`app/core/metrics.py`) are in-memory. Run **one** uvicorn process
  behind a load balancer. Adding more processes without a shared rate-limit
  store weakens the limits and splits the metrics; plan a Redis-backed limiter
  before scaling horizontally.
- **Immutable financial records.** Never edit or reverse via SQL. Use the
  service-level reversal endpoint; the database triggers reject direct writes.
- **Append-only webhook inbox.** Callbacks are deduplicated at the database.

## Environment variables

All `CHAMACORE_` variables are read from the environment or `.env`
(see `app/core/config.py` for defaults and validation).

| Variable | Required in prod | Purpose |
|----------|------------------|---------|
| `CHAMACORE_DEBUG` | `false` | Disables dev-only secrets and enable dev credential master key |
| `CHAMACORE_DATABASE_URL` | yes | SQLAlchemy/PostgreSQL URL e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `CHAMACORE_JWT_SECRET_KEY` | yes | Strong random secret for access tokens |
| `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY` | yes | Base64-encoded 32-byte AES key for provider credentials |
| `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY_VERSION` | no | Rotates the active key (default `1`) |
| `CHAMACORE_CREDENTIAL_ENCRYPTION_KEYS` | no | JSON map of older key versions for rotation |
| `CHAMACORE_PUBLIC_BASE_URL` | yes | Public base URL for provider callbacks |
| `CHAMACORE_GENERAL_API_PER_MINUTE_LIMIT` | no | General API rate limit per client IP per minute (default 300) |
| `CHAMACORE_AUTH_*_PER_MINUTE_LIMIT` | no | Auth endpoints limits (register/token/member-link) |
| `CHAMACORE_PAYMENT_*_PER_MINUTE_LIMIT` | no | Payment validate/initiate/webhook limits |
| `CHAMACORE_PAYMENT_WEBHOOK_MAX_BODY_BYTES` | no | Webhook body cap (default 262144) |
| `CHAMACORE_PROVIDER_HTTP_TIMEOUT_SECONDS` | no | Outbound provider HTTP timeout |
| `CHAMACORE_PAYMENT_ATTEMPT_MAX_RETRIES` | no | Payment attempt retries (default 2) |
| `CHAMACORE_PAYMENT_INITIATE_DAILY_LIMIT` | no | Daily initiation budget per connection |

Fail-closed behaviour: with `CHAMACORE_DEBUG=false`, the app **refuses to
start** if the JWT secret is the development default or the credential
encryption key is missing/development-only.

## Secrets

- Never store secrets in `app/` code or in the repository. Use a secret
  manager and inject via environment variables.
- Generate a credential key: `python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"`
- Rotate `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY` by bumping the version and
  supplying the old key in `CHAMACORE_CREDENTIAL_ENCRYPTION_KEYS`.

## Deploy

```bash
# Build and start app + PostgreSQL (dev-style compose)
docker compose up --build -d
docker compose ps
```

Manual deployment:

```bash
python -m venv env && source env/bin/activate
pip install -r requirements.txt   # or: pip install -r requirements.lock.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Database migrations

Run `alembic upgrade head` **before** rolling out new code so the new schema
is in place when it reads. Every schema change ships a migration; never hand-
edit production tables.

## Backups

PostgreSQL:

```bash
pg_dump -Fc -d "postgresql://user:pass@host:5432/db" -f chamacore.backup
pg_restore -d "postgresql://user:pass@host:5432/db" chamacore.backup
```

Test restores regularly. SQLite is development-only and is not a backup
strategy for the ledger.

## Monitoring

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness; no database check |
| `GET /ready` | Readiness; verifies database connectivity |
| `GET /metrics` | Prometheus text exposition of HTTP request counters and latency |
| `/docs` | OpenAPI/Swagger |

Scrape `http://<host>:8000/metrics` in application header namespaces
(`chamacore_http_requests_total`, `chamacore_http_request_duration_seconds_*`).

## Logging and correlation

Logs are single-line JSON on stdout/stderr. Every record carries a
`request_id` correlation id (default `-` outside requests). Clients may supply
their own id with the `X-Request-ID` header; the app echoes it on responses.
Forward `X-Request-ID` from your reverse proxy or client so a single user
event can be traced across proxies, the API, and provider calls.

Example: `{"timestamp": "...", "level": "INFO", "logger": "app.request", "request_id": "corr-123", "message": "request complete", "method": "GET", "path": "/health", "status": 200, "duration_ms": 1.2, "client": "127.0.0.1"}`

## Rate limiting

Limits are keyed by client IP on a fixed one-minute window (per process):

- General API: `CHAMACORE_GENERAL_API_PER_MINUTE_LIMIT` (300)
- Auth: register 10, token 30, member-link 10 per minute
- Payments: validate 5/min, initiate daily 5000, webhook 60/min
- C2B callbacks: rate-limited like webhooks (per connection, per client IP)

Reaching a limit returns `429` with `detail.code = "RATE_LIMITED"`. If you
scale to multiple processes, move the limiter to a shared store first.

## Daraja C2B (manual Paybill) activation

C2B lets members pay a Chama's Paybill shortcode directly from their M-Pesa
menu. Until the reference-matching rule is decided (OQ-021) it runs
**fail-closed**:

- The C2B Validation URL always answers `ResultCode = 1` (reject) and records
  the arrival as a `REJECTED` payment event.
- The C2B Confirmation URL acknowledges and stores the payment idempotently
  but never writes a ledger entry.

To activate for one Chama's connection (after the connection is created):

```bash
export CHAMACORE_PUBLIC_BASE_URL="https://your-domain"          # default http://localhost:8000
export CHAMACORE_EMAIL="chair@example.com" CHAMACORE_PASSWORD="***"
export CHAMACORE_CHAMA_ID="<chama-uuid>"
python scripts/register_daraja_c2b_urls.py \
  --connection-id <payment-connection-id> \
  --response-type Completed
```

The script logs in as the chairperson and calls the authenticated
register-URL endpoint; the server derives each connection's callback token
(ADR-018) and points Safaricom's Validation/Confirmation URLs at
`/api/v1/payments/c2b/validate/{connection_id}` and
`/api/v1/payments/c2b/confirm/{connection_id}`.

Verification: trigger a manual KES payment to the shortcode. Expect a
`ResultCode: 1` rejection response and a `REJECTED` or `PROCESSED` row in
`payment_events`; nothing on the ledger. Activation is safe to re-run; each
connection's callback sits behind its own token.

## Operational checklist

- [ ] `CHAMACORE_DEBUG=false`, real JWT secret, real credential key set
- [ ] Migrations applied before code rollout
- [ ] Behind TLS-terminating reverse proxy
- [ ] Backups configured and restore-tested
- [ ] Prometheus scraping `/metrics`, alerting on `count_total` and 5xx rate
- [ ] `X-REQUEST-ID` forwarded by the proxy
- [ ] Single uvicorn process (or shared rate-limit store when scaled)