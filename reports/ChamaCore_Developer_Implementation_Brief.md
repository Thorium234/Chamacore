# ChamaCore — Developer Implementation Brief

**For:** Implementing developer  
**Based on:** Repository review at HEAD `609eb61` (2026-09-22)  
**Scope:** Security hardening, functionality gaps, and core business follow-ups  
**Out of scope for this brief:** Redis / shared rate-limit store / multi-process limiter migration  

---

## 1. Context (do not rework)

These are **already implemented**. Do not rewrite them unless a bug is found.

- V1: auth, chamas, members, roles, contributions, shares  
- V2: immutable ledger, chart of accounts seed (`1000` Cash, `3000` Share Capital, `4000` Registration Fees), contribution confirm/reverse → ledger (ADR-014)  
- V3: Daraja-only provider, sealed connections, STK intents, webhook inbox  
- C2B + STK settlement to contribution + ledger (ADR-019 / OQ-021)  
- CORS via `CHAMACORE_CORS_ORIGINS` (explicit origins, not `*`)  
- Fail-closed JWT + credential encryption keys when `CHAMACORE_DEBUG=false`  
- In-process rate limits, JSON logs, `/metrics`, production runbook  

**Rule (AGENTS.md):** If a business rule is open, do not invent it. Record in `docs/decisions/OPEN_QUESTIONS.md` and stop.

---

## 2. Implementation priorities

| Priority | Theme | Goal |
|----------|--------|------|
| **P0** | Production safety | Safer defaults and ops before real money traffic |
| **P1** | Core business completeness | Registration-fee money path + readable balances |
| **P2** | Product depth | Loans/payouts only after OQs; notifications; audit surface |

Work **smallest possible diffs**. Prefer new services/endpoints over rewriting payment or ledger cores.

---

## 3. P0 — Production safety (implement first)

### 3.1 JWT access-token lifetime

**Problem:** Default `jwt_expires_minutes = 60 * 24` (24 hours) is long for a financial API.

**Implement:**

1. Reduce default access-token lifetime (suggested: **60** or **120** minutes). Keep configurable via `CHAMACORE_JWT_EXPIRES_MINUTES`.  
2. Document the change in README / production runbook.  
3. **Optional but preferred:** add a refresh-token flow:
   - Opaque or signed refresh token with longer TTL  
   - Store hashed refresh tokens server-side (or rotate on use)  
   - Endpoint: `POST /api/v1/auth/refresh`  
   - Endpoint: `POST /api/v1/auth/logout` (revoke refresh)  
4. If refresh is deferred, still shorten access TTL and note that clients must re-login.

**Do not:** change password hashing or membership claim rules.

**Tests:** token expires after configured window; old tokens rejected; (if refresh) rotate and revoke behaviour.

---

### 3.2 Protect `/docs` and `/redoc` in production

**Problem:** OpenAPI UI is useful in dev; in production it expands the attack surface.

**Implement:**

1. When `CHAMACORE_DEBUG=false`, disable docs, e.g.:

```python
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
```

2. Note in production runbook that API contract is sourced from docs in repo / staging, not public prod UI.

**Tests:** with debug true, `/docs` 200; with debug false, `/docs` 404.

---

### 3.3 Restrict `/metrics` exposure

**Problem:** `GET /metrics` is unauthenticated.

**Implement (pick one, document it):**

- **A (preferred for single-host):** serve metrics only when `CHAMACORE_DEBUG=true`, **or** require a shared secret header e.g. `X-Metrics-Token` matching `CHAMACORE_METRICS_TOKEN`.  
- **B:** leave endpoint public but document that the reverse proxy must not expose `/metrics` to the internet (private scrape network only).

If choosing A with token:

```text
CHAMACORE_METRICS_TOKEN=<random>
```

Missing/wrong token → `404` or `401` (prefer **404** to avoid advertising the endpoint).

**Tests:** authorized scrape returns Prometheus text; unauthorized does not leak series.

---

### 3.4 Production env checklist (ops, not code — verify in runbook)

Ensure `docs/12_PRODUCTION_RUNBOOK.md` and `.env.example` clearly list:

| Variable | Prod expectation |
|----------|------------------|
| `CHAMACORE_DEBUG` | `false` |
| `CHAMACORE_JWT_SECRET_KEY` | strong random |
| `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY` | base64 32-byte |
| `CHAMACORE_DATABASE_URL` | PostgreSQL |
| `CHAMACORE_PUBLIC_BASE_URL` | `https://api.example.com` |
| `CHAMACORE_CORS_ORIGINS` | exact frontend origin(s), no `*` |

Add a short “pre-go-live” checklist if missing: TLS at proxy, `alembic upgrade head` before traffic, single uvicorn process note (existing architecture).

**No Redis work in this brief.**

---

### 3.5 Security headers (proxy or app)

**Prefer reverse proxy** (nginx/Caddy) for:

- `Strict-Transport-Security`  
- `X-Content-Type-Options: nosniff`  
- `Referrer-Policy`  

Optional minimal Starlette middleware only if the team has no proxy control. Do not invent a large security middleware stack.

---

### 3.6 System-user posting guard

**Context:** Settlements run as seeded `system@chamacore.invalid`.

**Implement / verify:**

1. System user **cannot** obtain a JWT via `/auth/token` (password is non-login).  
2. No public endpoint accepts `actor_id` override to the system user.  
3. Only internal service code paths (C2B confirm, STK settlement) load the system user for posting.

**Tests:** login as system email fails; contribution confirm by normal chair still works; C2B/STK settlement tests remain green.

---

## 4. P1 — Core business functionality

### 4.1 Registration-fee payments on the ledger (OQ-014)

**Status:** Open question — **do not implement posting rules until OQ-014 is decided.**

**Developer actions:**

1. If product has not decided: leave blocked; optionally draft questions for the product owner (see §7).  
2. If product **approves** a decision, record ADR + close OQ-014, then implement in a **small** slice:
   - Status flow for fee payment (e.g. OWED → PAID)  
   - Ledger: DR Cash / CR Registration Fees (`4000`) or whatever the ADR specifies  
   - Idempotency key pattern consistent with contribution posting  
   - Optional: link fee payment to STK/C2B purpose later  

**Do not:** invent fee amounts or waive rules beyond existing V1 waive behaviour.

---

### 4.2 Ledger-backed balances and simple statements

**Problem:** Ledger posts exist; members/chairs cannot easily read “my balance” or “Chama cash position.”

**Implement (read-only; no new business inventing):**

1. **Account balance** helper: sum entries for a ledger account (respect existing entry model).  
2. Endpoints (authorize Chama-scoped as elsewhere), for example:
   - `GET /api/v1/chamas/{chama_id}/ledger/accounts` — list accounts + computed balances  
   - `GET /api/v1/chamas/{chama_id}/ledger/accounts/{account_id}/entries` — cursor pagination if needed  
3. Optional member view: contribution history is already partly there; add **confirmed contribution total** or share units summary if it maps cleanly to existing data.

**Constraints:**

- Use Decimal; never float.  
- Do not denormalize balances into mutable columns unless an ADR says so.  
- Read path only — no “adjust balance” API.

**Tests:** after confirm contribution, Cash and Share Capital balances move as expected; unauthorized user gets 403.

---

### 4.3 C2B / STK edge-case hardening (functionality)

Review and add tests (fix bugs if found; do not expand scope):

| Case | Expected behaviour (per ADR-019) |
|------|----------------------------------|
| Unknown `BillRefNumber` | Validation reject |
| Inactive membership | Validation reject |
| Inactive connection | Validation reject |
| Duplicate `TransID` | Idempotent; no double contribution |
| STK success without `contribution_id` | Define per existing code — do not invent; document |
| STK success with already CONFIRMED contribution | Idempotent no-op on ledger |

If any case is ambiguous, open a short note in OPEN_QUESTIONS rather than guessing.

---

## 5. P2 — Later product work (only after decisions)

### 5.1 Loans and payouts (OQ-015 … OQ-020)

**Blocked.** Do not implement loan principal, interest, schedules, or payouts until product closes those questions and ADRs exist.

When unblocked, expect: new accounts in chart, posting services, approval rules — separate milestone.

### 5.2 Notifications

Out of core ledger path. If scheduled:

- Abstraction (port) for SMS/email  
- Triggers: contribution confirmed, STK failed, role assigned  
- No secrets in repo; provider keys in env  

### 5.3 Audit event table

Optional product/security enhancement:

- Append-only `audit_events` (actor, action, entity, metadata, request_id)  
- Write on sensitive mutations (role change, connection enable, contribution reverse)  
- Read API chairperson-only  

Do not replace the ledger with audit logs.

### 5.4 Frontend / USSD

Out of this backend brief. CORS is already ready for a separate SPA.

---

## 6. Explicit non-goals (this brief)

- **Redis** or any shared rate-limit backend  
- Multi-worker rate-limit redesign  
- Rewriting Daraja adapter or payment state machines  
- Removing Jenga source tree (leave unregistered)  
- Inventing loan/payout/registration-fee rules while OQs are open  
- Full bank reconciliation or external reporting suite  

---

## 7. Questions for product (if implementing OQ-014+)

Share with product owner before coding fee payments:

1. When a member pays the registration fee via M-Pesa, should it post **DR Cash / CR Registration Fees (4000)** for the full fee amount?  
2. Does payment auto-mark the fee **PAID**, or is a chair confirmation still required?  
3. Can fees be paid partially?  
4. Is waive still allowed after a partial payment?  

For loans/payouts, use existing OPEN_QUESTIONS OQ-015–020 as the agenda.

---

## 8. Suggested implementation order

```text
1. JWT TTL reduction (+ optional refresh)     [P0]
2. Disable docs/openapi when not debug       [P0]
3. Metrics protection (token or proxy doc)   [P0]
4. System-user login/posting verification    [P0]
5. Runbook / .env.example polish             [P0]
6. Ledger balance + account list endpoints   [P1]
7. C2B/STK edge-case test pass               [P1]
8. OQ-014 decision → fee payment posting     [P1 when decided]
9. Notifications / audit / loans             [P2 later]
```

---

## 9. Definition of done (per item)

- [ ] Smallest diff that solves the item  
- [ ] Tests added or updated; `pytest` green  
- [ ] No new open business rules invented  
- [ ] README or runbook updated if env/behaviour changes  
- [ ] ADR only when a product decision is required (OQ-014+)  

---

## 10. Reference paths

| Area | Location |
|------|----------|
| Settings / CORS / JWT | `app/core/config.py` |
| App entry / middleware | `app/main.py` |
| Ledger posting | `app/services/ledger.py` (and related) |
| C2B | `app/services/c2b_payment.py`, `app/api/v1/c2b.py` |
| Open questions | `docs/decisions/OPEN_QUESTIONS.md` |
| Production ops | `docs/12_PRODUCTION_RUNBOOK.md` |
| Status | `docs/00_PROJECT_STATUS.md` |

---

*Brief prepared for handoff to an implementing developer. Redis and horizontal rate-limit work are intentionally excluded.*
