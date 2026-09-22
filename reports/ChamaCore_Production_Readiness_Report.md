# ChamaCore — Production Readiness & Gap Report

**Repository:** https://github.com/Thorium234/Chamacore  
**HEAD:** `d034500` — C2B manual Paybill intake  
**Report date:** 2026-09-17  
**Audience:** Developer / operator preparing a production push with a frontend and Daraja

> **Addendum (22 Sep 2026).** The decisions this report said were missing are
> now resolved and implemented (ADR-014 approved, ADR-019 added; OQ-012,
> OQ-013, OQ-021 closed):
>
> - Every Chama is seeded with a default chart of accounts — `1000` Cash
>   (ASSET), `3000` Share Capital (EQUITY), `4000` Registration Fees
>   (REVENUE) — at creation; existing Chamas are backfilled by migration
>   `f2b4d6a8e0c1`.
> - Confirming a contribution posts DR Cash / CR Share Capital idempotently
>   (source `CONTRIBUTION_CONFIRMATION:<id>`); reversing one posts a
>   compensating reversal.
> - C2B validation now resolves `BillRefNumber` (the server-assigned
>   membership number) against an ACTIVE membership on an ACTIVE connection;
>   C2B confirmation creates/settles the current-period contribution and
>   posts to the ledger (`TransID`-idempotent).
> - Succeeded STK payment intents settle their linked contribution; manual
>   and system-triggered settlements run as the seeded, non-login system user
>   (`system@chamacore.invalid`).
>
> Rows below marked **Open / Plumbing only / Not wired** for OQ-012, OQ-013,
> OQ-021, C2B, and STK-settlement are superseded by the above. Loans,
> payouts, and registration-fee payments (OQ-014..OQ-020) remain open, as do
> the operator-configuration items (secrets, HTTPS public URL).

---

## 1. Executive summary

ChamaCore’s backend for **membership, contributions (domain records), STK payment intents, and C2B intake plumbing** is largely in place. Several items are still missing or intentionally incomplete before a full “money lands on the books + SPA works” production story:

| Gap | Status | Blocks |
|-----|--------|--------|
| **CORS for frontend** | **Missing** | Browser SPA talking to API |
| **C2B validate/confirm** | **Plumbing only** | Accepting Paybill money (always rejects validation; confirm stores event, no ledger) |
| **OQ-021** BillRef → member/Chama | **Open** | C2B accept path + matching |
| **OQ-012 / OQ-013** chart of accounts + contribution posting | **Open** | Any money → ledger |
| **STK callback → contribution/ledger** | **Not wired** | STK success does not settle member contribution on books |
| **Production secrets & HTTPS public URL** | **Operator config** | Real Daraja callbacks + secure deploy |

**Honest production stance today**

- You **can** deploy the API for auth, chamas, members, contributions (as domain records), STK initiate/query, C2B event storage, health/metrics.
- You **cannot** yet claim full “Paybill accepted and credited to member ledger” or “STK success posts contribution to ledger.”
- You **must** add CORS before any separate frontend origin works.

---

## 2. What works today (verify in development first)

Do this **before** production. Treat green here as the baseline.

### 2.1 Local bootstrap

```bash
git pull origin main
python -m venv env && source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: keep CHAMACORE_DEBUG=true for local
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

Expect: migrations apply; `/docs` loads; suite in the ~230+ passing range (Jenga tests skipped by design).

### 2.2 Smoke checklist (dev)

| Check | How | Pass criteria |
|-------|-----|----------------|
| Liveness | `GET /health` | `{"status":"ok"}` |
| Readiness | `GET /ready` | `{"status":"ready"}` (DB up) |
| Auth | Register → token → `/api/v1/auth/me` | JWT works |
| Chama lifecycle | Create chama, member, membership, role | 2xx, authz holds |
| Contribution domain | Record / confirm / reverse contribution | Domain rules hold (shares per ADR-005) |
| Ledger engine | Post via ledger APIs (if you have seeded accounts) | Double-entry balances; reversals idempotent |
| Daraja connection | `scripts/create_daraja_connection.py` or API with sandbox creds | Connection created, sealed, validate |
| STK path | Create intent → initiate → status query (sandbox phone) | Attempt states advance; OAuth token cached |
| STK webhook | Public URL or status-query fallback | Event deduped in inbox |
| C2B register | `scripts/register_daraja_c2b_urls.py` (needs public URL for real Safaricom) | URLs registered |
| C2B validate | POST validate path | **ResultCode 1** (fail-closed) + event stored |
| C2B confirm | POST confirm path | Event stored idempotently by `TransID`; **no ledger row** |
| Metrics / logs | `GET /metrics`; JSON logs with `request_id` | Present |

### 2.3 Known correct limitations in dev

- C2B validation **always rejects** until OQ-021.
- C2B confirmation **never** writes the ledger until OQ-012/013 + OQ-021.
- STK success advances payment state machines only; it does **not** auto-confirm a contribution or post ledger entries (same open questions).
- CORS is absent: browser calls from `localhost:3000` → `localhost:8000` will fail until CORS is added.

---

## 3. What we do not have — implement before / for production

### 3.1 CORS (required for frontend) — **implement now**

**Status:** Not present in `app/main.py`.

**Why:** Browser same-origin policy blocks a SPA on another origin from calling the API.

**Do not ship production with:**

```python
allow_origins=["*"]  # unsafe with credentials / JWT
```

**Minimal production-safe approach**

1. Add config (env-driven):

```python
# app/core/config.py
cors_origins: str = "http://localhost:3000,http://localhost:5173"

@property  # or a method used at startup
def cors_origin_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

2. Register middleware early in `app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
```

3. Environment:

```bash
# Dev
CHAMACORE_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Prod
CHAMACORE_CORS_ORIGINS=https://app.yourdomain.com
```

4. Document in `.env.example` and `docs/12_PRODUCTION_RUNBOOK.md`.

**CORS vs Daraja:** Safaricom → API is server-to-server. CORS does **not** apply to STK/C2B callbacks. CORS is only for the **frontend**.

---

### 3.2 C2B — present as plumbing, incomplete product path

| Capability | Status |
|------------|--------|
| Validate URL endpoint | Implemented — **always ResultCode 1** |
| Confirm URL endpoint | Implemented — store + idempotency only |
| Register URLs (chairperson + script) | Implemented |
| Token binding / rate limits / schemas | Implemented |
| Accept payment for known member | **Blocked by OQ-021** |
| Credit ledger | **Blocked by OQ-012/013 (+ OQ-021)** |

**Safe production behaviour today:** register C2B URLs only if you accept that **manual Paybill payments will be rejected at validation** (or confirm-stored without books) until product rules exist. Prefer keeping C2B registration **off** in production until OQ-021 is decided, unless the goal is only to prove callback reachability.

---

### 3.3 Open questions that must be decided (not coded blindly)

#### OQ-012 — Chart of accounts

When a Chama is created, which ledger accounts exist (cash, member shares, fees, etc.)?

**Blocked:** seeding accounts; any automated posting.

#### OQ-013 — Contribution posting mapping

On confirmed contribution: which account is debited, which credited?

**Blocked:** contribution → ledger link; true cashbook balances.

#### OQ-021 — C2B BillRef matching

- What is in `BillRefNumber`? (e.g. membership number)
- One shortcode per Chama vs shared shortcode?
- Validation rules (ACTIVE membership, ACTIVE connection)?

**Blocked:** C2B accept logic; meaningful confirm processing.

**Also blocked by the same cluster:** STK callback “settle contribution record” — today only payment intent/attempt state changes.

**Recommended decision order for money-in completeness**

1. OQ-012 (accounts)  
2. OQ-013 (contribution mapping)  
3. OQ-021 (BillRef + C2B accept)  
4. Wire STK success → contribution confirm → ledger post  
5. Wire C2B confirm → same posting path  

---

### 3.4 Production configuration & ops (must have for go-live)

| Item | Action |
|------|--------|
| `CHAMACORE_DEBUG=false` | Required; fail-closed on default JWT / missing encryption key |
| `CHAMACORE_JWT_SECRET_KEY` | Strong random secret |
| `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY` | Base64 32-byte key |
| `CHAMACORE_DATABASE_URL` | PostgreSQL only in prod (not SQLite) |
| `CHAMACORE_PUBLIC_BASE_URL` | `https://api.yourdomain.com` (reachable by Safaricom) |
| `CHAMACORE_CORS_ORIGINS` | Explicit frontend origin(s) after CORS is implemented |
| TLS | Terminate at reverse proxy (nginx/Caddy/cloud LB) |
| Migrations | `alembic upgrade head` **before** traffic |
| Process model | **One** uvicorn worker until Redis-backed rate limits exist |
| Backups | `pg_dump` + restore test |
| Monitoring | Scrape `/metrics`; alert on 5xx; forward `X-Request-ID` |

Generate encryption key:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

---

### 3.5 Frontend-related (beyond CORS)

| Item | Notes |
|------|--------|
| Auth header | `Authorization: Bearer <token>`; include in CORS `allow_headers` |
| Token storage | Prefer memory / httpOnly cookie strategy discussed with SPA; avoid long-lived tokens in `localStorage` if possible |
| API base URL | Point SPA at production API origin |
| Error shape | API uses `detail: { code, message }` for `AppError` — handle in UI |
| Rate limits | 429 with `RATE_LIMITED` — show retry UX |
| No public secret | Never put Daraja keys or JWT secret in frontend |

---

### 3.6 Daraja production path

| Step | Detail |
|------|--------|
| App on Safaricom portal | Production app + production shortcode/passkey |
| Connection in ChamaCore | `environment: PRODUCTION`, sealed credentials |
| Callbacks | Built from `CHAMACORE_PUBLIC_BASE_URL` |
| STK | Intent → initiate → webhook/status query |
| C2B | Only after OQ-021 (or accept fail-closed) |
| Token cache | Already ~50 minutes per consumer key — good for prod |

---

## 4. Prioritized implementation backlog

### P0 — Before any frontend in production

1. **Implement CORS** (config + middleware + `.env.example` + runbook).  
2. **Prod env + Postgres + TLS + single process** per runbook.  
3. **Dev verification** of auth, chamas, STK sandbox, health/ready/metrics.  
4. **Do not** enable live C2B accept until OQ-021 (optional: leave registration off).

### P1 — Before claiming “payments complete”

5. Decide **OQ-012** and **OQ-013**; implement account seeding + contribution → ledger.  
6. Decide **OQ-021**; implement C2B accept + member match; confirm → same posting path.  
7. Wire **STK success** → contribution settlement → ledger (same rules).  
8. Sandbox then production dry-run of full money-in paths.

### P2 — Scale and polish (not blockers for first controlled deploy)

9. Redis (or equivalent) for multi-worker rate limits and metrics.  
10. Daraja token cache already done; revisit pool sizes / indexes under load.  
11. Optional: small admin UI for payment events / rejected C2B.  
12. Loans/payouts (OQ-015–020) remain later.

---

## 5. What you can push to production *now* (controlled scope)

**In scope if gaps above are accepted:**

- User auth, chamas, members, roles, registration fees, contribution **records** (not ledger-backed balances).  
- Payment connections (Daraja), STK initiate/status/webhook **state machine**.  
- C2B endpoints **fail-closed** (events only).  
- Observability: health, ready, metrics, structured logs.  
- Frontend **only after** CORS is merged and origins configured.

**Out of scope until OQs closed:**

- “Member paid Paybill and balance updated on ledger.”  
- “STK success automatically confirmed contribution on books.”  
- True financial reports from the ledger for day-to-day Chama cash.

Communicate that clearly to stakeholders so production is not sold as full M-Pesa settlement.

---

## 6. Suggested production go-live checklist

### Engineering

- [ ] CORS implemented with explicit origins (no `*`)  
- [ ] `pytest` green on HEAD  
- [ ] Dev smoke checklist (section 2) passed  
- [ ] Postgres provisioned; `alembic upgrade head`  
- [ ] Secrets injected (JWT, encryption key, DB URL)  
- [ ] `CHAMACORE_DEBUG=false` verified (app starts)  
- [ ] `CHAMACORE_PUBLIC_BASE_URL` HTTPS public  
- [ ] Reverse proxy TLS; single uvicorn process  
- [ ] `/health`, `/ready`, `/metrics` monitored  
- [ ] Backup + restore tested  

### Product / payments

- [ ] Daraja production credentials on a PRODUCTION connection  
- [ ] One successful **sandbox** STK cycle documented  
- [ ] C2B: either **disabled** or accepted as fail-closed until OQ-021  
- [ ] Stakeholder sign-off: ledger posting still blocked by OQ-012/013  

### Frontend

- [ ] SPA origin listed in `CHAMACORE_CORS_ORIGINS`  
- [ ] Login + authenticated calls work cross-origin  
- [ ] 401 / 429 handling verified  

---

## 7. Closing recommendation

1. **This week:** Add CORS (minimal, config-driven), finish **dev** verification of everything that already exists, deploy API to production with **honest scope** (no full C2B/ledger settlement claims).  
2. **Next product cycle:** Close OQ-012 → OQ-013 → OQ-021, then implement posting and C2B accept in small, test-backed slices.  
3. **Do not** invent BillRef or chart-of-accounts rules in code; record decisions in `OPEN_QUESTIONS.md` / ADRs first (project rule).

The codebase is strong enough for a **controlled production API + frontend** once CORS and ops secrets are in place. Full M-Pesa-to-ledger product completeness is **one product-decision cycle away**, not a rewrite.

---

*Based on public repository state at commit `d034500` (2026-09-17).*
