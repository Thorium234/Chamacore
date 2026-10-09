

```markdown
# ChamaCore — Production readiness & ops implementation brief

**Audience:** Backend / platform agent  
**Goal:** Implement migration safety, session security, retention, support playbooks, session UX, legal docs checklist, and architecture documentation **without** rewriting product features.  
**Constraint:** Surgical changes only. Prefer docs + small hardening hooks over large refactors.

---

## 0. Principles

1. **No full outage for schema change** — migrations must be online-safe (expand → migrate → contract).
2. **Rollback is designed before migrate** — never “figure it out after.”
3. **Staging first** — production migration only after a successful staging run on a production-like copy.
4. **Document decisions and failures** — working software without runbooks is not production-ready.
5. **Do not invent legal text** — create templates/placeholders and checklist; counsel reviews before publish.

---

## 1. Zero-downtime (online) database migrations

### 1.1 Deliverables

| Deliverable | Description |
|-------------|-------------|
| Migration playbook | How to add/drop/rename columns and change relationships without taking the app offline |
| Online migration script pattern | Expand → dual-write/backfill → switch reads → contract |
| Staging dry-run procedure | Steps + success criteria |
| Rollback plan template | Written **before** any production migration starts |

### 1.2 Online migration rules (implement as docs + Alembic conventions)

**Never in one step on large tables:**

- Drop a column the running app still reads
- Rename a column in place without dual-read
- Add a non-nullable column without a default/backfill
- Rewrite FKs in a long exclusive lock

**Preferred pattern:**

1. **Expand** — add new column/table/nullable FK; deploy app that writes both old and new (or reads new with fallback).
2. **Backfill** — batch job; no long locks; idempotent.
3. **Switch** — app reads from new shape only.
4. **Contract** — drop old column/table in a later release after verification.

### 1.3 Migration script requirements

For each production migration package, include:

- [ ] Forward Alembic revision (expand-only if high risk)
- [ ] Explicit **lock/timeout** notes (Postgres: short `lock_timeout` / `statement_timeout` where applicable)
- [ ] Backfill command or revision that is **restartable**
- [ ] Verification queries (row counts, null checks, FK integrity)
- [ ] **Rollback plan** (section 1.4) filled in before start

### 1.4 Rollback plan (mandatory before start)

Template to fill per migration:

```text
Migration ID:
Author:
Staging run date / result:
Forward steps:
Rollback steps (in order):
  1. ...
  2. ...
Data that cannot be restored:
Communication / freeze window (if any):
Owner on-call:
```

Rules:

- Rollback must restore **previous app version + previous schema compatibility**, not only “alembic downgrade” when data was transformed.
- If rollback is impossible after contract phase, state that clearly and require dual-run period before contract.

### 1.5 Staging environment

| Requirement | Detail |
|-------------|--------|
| Staging DB | Restored from anonymized or recent prod-like snapshot |
| App config | Staging secrets; same migration path as prod |
| Run order | `alembic upgrade` → backfill → smoke tests → only then prod |
| Smoke tests | Auth login, create intent, list chamas, webhook health, critical reads |
| Gate | No prod migration without green staging report |

---

## 2. Authentication & session management

### 2.1 Session revocation on password change

**Requirement:** When a user changes password, **all other active sessions end immediately**.

Implement / verify:

- On `change_password`: revoke **all** refresh tokens for that user (already intended in codebase — verify and test).
- Access tokens are short-lived; document residual window (`expires_in`).
- Optional hardening: version `token_version` / `password_changed_at` on User and reject access JWTs issued before that timestamp (if not already present).

**Acceptance:**

- [ ] Session A changes password → Session B refresh fails and API calls with B’s access token fail after access expiry or immediately if token version enforced
- [ ] Current session can continue only with tokens issued after change (product choice: either force re-login everywhere or keep only the changing client)

### 2.2 Account deletion — “Delete my account”

**Requirement:** User-initiated delete triggers a **data retention policy engine**, not silent hard-delete of financial history.

#### A) Retention policy engine (design + minimal implementation)

| Concept | Behavior |
|---------|----------|
| Request | User confirms delete → account enters `PENDING_DELETION` / deactivated login |
| Immediate | Revoke all sessions; block login; stop marketing/notifications |
| Retain | Ledger, payments, contributions, audit events per legal/ops schedule |
| Erase / anonymize | PII fields (email, phone display, name) after schedule or where law allows |
| Admin | Platform can see deletion state for support |

#### B) Retention schedule mapped to obligations

Document a table (fill with counsel later; engineer creates structure):

| Data class | Examples | Retain for | Action after |
|------------|----------|------------|--------------|
| Auth credentials | password hash, refresh tokens | Until delete + short grace | Destroy |
| Identity PII | email, phone, national ID | Per policy / KYC rules | Anonymize or retain if required |
| Financial ledger | postings, shares, loans | Long (tax/dispute) | Retain; detach from login |
| Payment provider refs | CheckoutRequestID, receipts | Per PSP + dispute window | Retain |
| Audit / security logs | auth events, admin actions | Security policy | Retain then purge |
| Notifications | inbox copy | Short | Delete or anonymize |

**Acceptance:**

- [ ] Delete account API + state machine documented
- [ ] No orphan “login still works” after delete request
- [ ] Financial rows not casually hard-deleted in v1

---

## 3. Support playbook (customer & payments)

Create **`docs/SUPPORT_PLAYBOOK.md`** (or `docs/ops/SUPPORT_PLAYBOOK.md`).

### 3.1 Structure (required sections)

1. **Severity levels** (SEV1 payment/money wrong → SEV4 cosmetic)
2. **Where to look** (logs, DB tables, provider dashboard, ngrok/callbacks)
3. **Auth issues** (login fail, must_change_password, deactivated user)
4. **Chama access** (PENDING chama, not a member, wrong active membership)
5. **Payments**
   - Customer charged twice
   - STK sent but no confirmation
   - Payment SUCCEEDED but no contribution/shares
   - `PHONE_FORMAT` / `DARAJA_*` errors
6. **Webhooks** (callback not received, duplicate events, DISAGREEMENT)
7. **Escalation** (who, what data to capture: user id, chama id, intent id, CheckoutRequestID, timestamps)

### 3.2 Double charge — investigation checklist

When customer reports double charge:

1. Collect: phone, approximate time, amount, Chama name, screenshots / M-Pesa SMS.
2. Find `payment_intent` / `payment_attempt` by membership + time + amount.
3. Check provider receipt / `CheckoutRequestID` / `MerchantRequestID` uniqueness.
4. Check `payment_events` for duplicate provider_event_id (dedup should prevent double settle).
5. If **two provider charges** → PSP/Safaricom path; refund policy applies; do not “fix” by posting twice in ledger.
6. If **one charge, two ledger posts** → bug; reconcile via documented correction path (no silent delete).
7. Record outcome in support ticket + audit note.

### 3.3 Payment failed — what to fix

| Symptom | Check | Typical fix |
|---------|--------|-------------|
| No STK prompt | Phone format, connection shortcode/passkey, initiate response body | Credentials / phone / connection |
| `DARAJA_*` | Adapter error mapping, Safaricom response | Message user; fix config |
| Accepted then failed | Callback ResultCode, customer cancel, timeout | Educate user; retry policy |
| Success, no shares | `contribution_id` / purpose / settlement path | Settlement job; purpose must include contribution |
| CORS / cannot reach API | `CORS_ORIGINS`, frontend base URL | Config only |

---

## 4. Session UX — warn before kill, preserve place

### 4.1 Requirements

1. **Warn before logout** when access token is near expiry (or refresh failed once).
2. User can **extend** session (silent refresh or “Stay signed in”).
3. If session ends, on next login **return to the same page** (deep link / `returnUrl`).
4. Do not destroy unsaved form state without warning when possible (local draft optional).

### 4.2 Implementation sketch

**Frontend**

- Store `returnPath` before forced logout.
- Banner: “You’ll be signed out in N minutes — Stay signed in.”
- On login success → navigate to `returnPath` if safe (same-origin path only).

**Backend**

- Reliable refresh rotation; clear errors when refresh revoked (password change / logout all).

**Acceptance:**

- [ ] Warning appears before access expiry when refresh is still valid
- [ ] Password change invalidates other devices
- [ ] Re-login returns user to prior route when `returnUrl` is internal

---

## 5. Legal & commercial documents (before production)

Create **`docs/legal/README.md`** checklist. Content is **counsel-owned**; agent creates structure and placeholders only.

| # | Document | Purpose | Owner |
|---|----------|---------|--------|
| 1 | Terms of Service | User rules, acceptable use, liability limits | Legal |
| 2 | Privacy Policy | Data collected, processors, rights | Legal |
| 3 | DPA (Data Processing Agreement) | Controller/processor for org customers | Legal |
| 4 | Refund Policy | M-Pesa/disputes, double charge, timelines | Legal + Product |
| 5 | Master Service Agreement | B2B customers if sold to orgs | Legal |
| 6 | Cyber liability insurance | Optional; vendor/policy reference | Ops / Founder |

**Agent tasks:**

- [ ] Folder + checklist + “not legal advice” banner
- [ ] Link placeholders from app footer when URLs exist
- [ ] Do **not** invent binding legal prose

---

## 6. Architecture & decision documentation

### 6.1 Architecture Decision Records (ADRs)

For each important choice, **one short paragraph** (or existing ADR file) covering:

- Context  
- Decision  
- Why (e.g. why Postgres/SQLite-dev, why split payment provider adapters, why endpoint exists)  
- Consequences / failure modes  

Minimum set to ensure exist or create stubs:

| Decision | Example “why” |
|----------|----------------|
| DB choice | Postgres for prod concurrency/constraints; SQLite dev only |
| Payment provider port | Daraja sandbox/prod isolation; credentials sealed |
| Membership vs Member | Person vs seat-in-Chama |
| JWT + refresh | Short access, revocable refresh |
| Online migrations | Expand/contract for zero downtime |
| Platform vs Chama roles | Tenant ops vs group money |

### 6.2 Local runbook

**`docs/LOCAL_DEVELOPMENT.md`** (or update README):

- Clone, `.env`, DB, `alembic upgrade head`, `uvicorn`, frontend `NEXT_PUBLIC_API_BASE_URL`
- Bootstrap platform admin if used
- Common failures (missing encryption key, CORS, wrong callback URL)

### 6.3 Failure modes

Document in **`docs/FAILURE_MODES.md`**:

| Failure | User impact | System behavior | Operator action |
|---------|-------------|-----------------|-----------------|
| Database down | API 5xx | No writes | Restart DB, check connections |
| Rate limit hit | 429 | Client backoff | Check abuse; raise limit if legitimate |
| Daraja down | STK fail | Safe error codes | Status page; retry later |
| Webhook unreachable | Pay pending | Poll/query STK status if available | Fix `PUBLIC_BASE_URL` / ngrok |
| Redis/cache (if any) | Degraded | Define fallback | … |

---

## 7. Implementation order for the agent

| Phase | Work | Output |
|-------|------|--------|
| **A** | Migration conventions + rollback template + staging checklist | `docs/ops/MIGRATIONS.md` |
| **B** | Verify/fix session revocation on password change; document token lifetime | Code + test + short note |
| **C** | Account deletion state + retention schedule table (engine skeleton) | API/docs |
| **D** | Support playbook (payments double-charge + fail paths) | `docs/SUPPORT_PLAYBOOK.md` |
| **E** | Frontend session warn / extend / returnUrl | FE only |
| **F** | Legal checklist placeholders | `docs/legal/` |
| **G** | ADRs + local run + failure modes | `docs/` |

Do **not** block on multi-Chama identity work in this brief unless already scheduled separately.

---

## 8. Definition of done

- [ ] Online migration playbook + rollback template exist and are used for the next schema change  
- [ ] Staging-first rule is written and referenced in AGENTS.md or ops docs  
- [ ] Password change revokes other sessions (tested)  
- [ ] Delete-account + retention schedule documented; no careless hard-delete of ledger  
- [ ] Support playbook covers double charge and payment failure  
- [ ] Session expiry warning + return-to-page on re-login  
- [ ] Legal doc checklist present (content may be TBD)  
- [ ] Architecture decisions and failure modes documented in one paragraph each where missing  

---

## 9. Out of scope (unless explicitly requested)

- Full rewrite of payment ledger  
- Writing final lawyer-approved ToS/Privacy  
- Purchasing cyber insurance  
- Multi-region active-active DB  

---

**End of brief.** Agent: implement in phases A→G; open PRs per phase; cite file paths in the completion report.
```