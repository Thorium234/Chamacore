# ChamaCore — Backend strategic plan

Scope: APIs, domain rules, persistence, auth, payments settlement, statements generation.
Do **not** own UI layout, role-specific screens, or client-only formatting beyond response contracts.

---

## 1. Goals (mapped to product problems)

| Product need | Backend responsibility |
|--------------|------------------------|
| Successful payment not visible in shares | Settlement path: payment → contribution/share posting is correct, queryable, idempotent |
| OTP first login, must change password | Auth model + OTP storage + forced password-change flag |
| Stronger password rules | Validation service (policy beyond length) |
| Developer / platform chama lifecycle | Platform admin APIs: activate / on-hold / terminate / reactivate |
| Login by email **or** phone **or** ID | Identity lookup + unique constraints + token issue |
| Role-scoped data | Authorization on every endpoint; filtered list/detail DTOs |
| More CRUD flexibility | Expand missing resources with clear authz |
| Phone `07xx` → `254…` | Canonical normalize on write (members, STK, C2B) |
| Contribution due notifications | Schedules + notification outbox (email/SMS/push later) |
| Pay from alternate MSISDN | Intent/C2B bind by **membership**, not payer phone alone |
| PDF statements | Server-side PDF generation + date-range API |
| Logos / avatars | File storage metadata + URLs (or signed URLs) |
| Transparency | Member-readable ledger/contribution/payment history APIs |
| Manual executive entry | Manual contribution/payment record APIs (audit who/when) |

---

## 2. Current baseline (already in codebase — build on, don’t rewrite)

- FastAPI layered API → services → repositories → models  
- Auth: email + password, JWT access + refresh  
- Chama, membership, roles, contributions, shares, ledger  
- Daraja **STK** (intent → initiate → callback) + **C2B** (validate/confirm, BillRef = membership number)  
- Payment connections, sealed credentials  
- CORS, public base URL for callbacks  

**Priority fix first:** chairperson payment success → contribution/share/ledger visibility (settlement + query contract).

---

## 3. Workstreams (ordered)

### W0 — Correctness: payment → shares visibility (P0)

**Problem:** Payment succeeds; chair does not see contribution/shares.

**Backend tasks**

1. Trace STK success path: webhook → intent SUCCEEDED → linked contribution CONFIRMED → share create → ledger post.  
2. Trace C2B confirm path: same settlement.  
3. Document when STK succeeds **without** contribution link (known no-op) and close the gap for “contribute” purpose.  
4. APIs for chair/member:
   - list contributions (filter by membership, period, status)
   - list shares for membership / chama
   - balances / recent ledger entries (read)
5. Ensure chair’s **own** membership contribution appears in the same queries used by UI.  
6. Tests: STK settle → contribution + share; C2B settle → same; duplicate callback idempotent.

**Deliverable:** Deterministic “money in → visible contribution/share” for the paying membership.

---

### W1 — Auth & identity flexibility (P0)

**Requirements:** OTP + forced password change; stronger passwords; login with email **or** phone **or** national ID.

**Backend tasks**

1. **Schema**
   - users: keep email nullable **or** add `login_identifiers`
   - `phone_number` (canonical `2547…`), `government_id` unique where set
   - `must_change_password` boolean
   - `otp_challenges` (user_id, code_hash, purpose, expires_at, consumed_at)
2. **Password policy service**
   - min length + complexity (upper/lower/digit/symbol) + block common passwords
   - apply on register, change-password, OTP-driven set
3. **Register**
   - accept at least one of: email, phone, government_id (+ password or OTP path)
   - normalize phone on write
4. **Login**
   - single endpoint: `username` = email **or** phone **or** ID + password  
   - resolve user, issue tokens; if `must_change_password`, return claim/flag so client redirects
5. **OTP**
   - generate, hash store, TTL, single-use
   - purposes: `FIRST_LOGIN`, `PASSWORD_RESET` (SMS/email provider adapter later; log in dev)
6. **Change password**
   - requires current password or valid OTP; clears `must_change_password`

**Out of scope for W1:** full SMS vendor production wiring (stub/provider port OK).

---

### W2 — Platform / developer chama lifecycle (P1)

**Requirement:** After chair creates chama, platform must activate / on-hold / terminate / reactivate before full operations.

**Backend tasks**

1. Chama status machine: e.g. `PENDING_ACTIVATION` → `ACTIVE` → `ON_HOLD` → `TERMINATED` (+ reactivate rules).  
2. Gate operations: payments, loans, membership changes only when `ACTIVE` (read-only when `ON_HOLD` as policy).  
3. **Platform admin** role (system-level, not chama chair):
   - list chamas, filter by status
   - PATCH status with reason + audit event
4. Audit every status transition.

**Note:** Chair “activate member” stays chama-scoped; platform lifecycle is separate.

---

### W3 — Role-based authorization & richer CRUD (P1)

**Requirement:** Member vs Chair vs Treasurer vs Secretary see different capabilities; expand CRUD.

**Backend tasks**

1. Centralize permission matrix (resource × action × role).  
2. Member: read own membership, own contributions/shares/loans; read **shared transparency** lists (group transactions) as **read-only**.  
3. Chair/Treasurer: CUD where policy allows (manual entry, confirm, reverse with rules).  
4. Expand endpoints only where product needs them (examples):
   - membership status transitions (active / on-hold / terminated) by authorized role
   - manual contribution record (amount, period, date, note, recorded_by)
   - chama settings: contribution schedule (day/amount/frequency)
5. Never rely on frontend hiding buttons alone.

---

### W4 — Phone normalization & alternate payer MSISDN (P1)

1. Shared `normalize_ke_msisdn()` on member create/update and payment initiate.  
2. STK: still send prompt to **intent phone** (member default or explicit `payer_phone` on initiate if allowed).  
3. Settlement: always credit **membership_id** on the intent / BillRef — not “whoever’s phone paid”.  
4. C2B: BillRef = membership number remains source of truth for who receives credit.

---

### W5 — Notifications (P2)

1. Chama contribution schedule (frequency, due day, amount).  
2. Notification outbox table: recipient, channel, template, payload, status.  
3. Job/cron: due reminders → enqueue.  
4. Delivery adapters later (SMS/email/FCM).

---

### W6 — Statements PDF (P2)

1. `GET .../statements?from=&to=&membership_id?`  
2. Aggregate contributions, payments, shares, ledger lines.  
3. Generate PDF server-side; return file or signed download URL.  
4. Authorization: member own; chair/treasurer chama-wide.

---

### W7 — Media (logos / avatars) (P2)

1. Upload endpoint (image constraints) → object storage or local dev disk.  
2. Store `avatar_url` / `logo_url` on member/chama.  
3. Default: no binary required — client can show initials if null.

---

### W8 — Transparency reads (P1–P2)

Authenticated members of chama:

- payment history (sanitized)
- contribution list
- ledger summary / recent transactions  
All **read**; mutations still role-gated.

---

## 4. Suggested API surface (additive)

| Area | Examples |
|------|----------|
| Auth | register (flexible ids), login (username+password), OTP request/verify, change-password |
| Platform | `/admin/chamas`, status transitions |
| Chama | settings, logo upload |
| Membership | status, avatar |
| Contributions | list, manual create, confirm/reverse (existing + gaps) |
| Payments | initiate with optional payer_phone; history |
| Statements | PDF by date range |
| Notifications | list preferences (optional) |

---

## 5. Data / security notes

- Hash OTPs; short TTL; rate-limit.  
- Password policy server-side.  
- Platform admin ≠ chama chair.  
- Audit: lifecycle, manual entries, reversals.  
- Idempotent payment settlement (existing ADR direction).

---

## 6. Implementation phases (backend)

| Phase | Focus |
|-------|--------|
| **B1** | W0 settlement + visibility APIs |
| **B2** | W1 auth (password policy, OTP flag, multi-identifier login) |
| **B3** | W3 authz matrix + manual contribution entry |
| **B4** | W2 platform chama lifecycle |
| **B5** | W4 payer phone flexibility |
| **B6** | W8 transparency list endpoints |
| **B7** | W5 notifications foundation |
| **B8** | W6 PDF + W7 media |

Each phase: migrate → service → API → tests. No full rewrite of payment or ledger cores.
