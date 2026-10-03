# ChamaCore Backend Gap Report
**Date:** 2026-10-03  
**HEAD context:** post-`a541db7` (statements, platform admin, notifications, phone helper, visibility APIs)  
**Audience:** backend developer — implement these on the API only; no full rewrite  

---

## Executive summary

Recent commits closed visibility APIs, platform admin, notifications, and partial password-change plumbing. **Five product-blocking gaps remain**, and two live STK errors (`PHONE_FORMAT`, `DARAJA_None`) are still reproducible.

| # | Gap | Severity | Status on HEAD |
|---|-----|----------|----------------|
| 1 | Strong password policy | High | **Missing** — only length/hash, no complexity service |
| 2 | Server-side `must_change_password` enforcement | High | **Partial** — flag + change endpoint exist; routes not gated |
| 3 | Chair payment → shares settlement | Critical | **Root cause identified** — settlement only if `contribution_id` linked |
| 4 | Phone normalize vs STK `PHONE_FORMAT` | Critical | **Mismatch** — lenient store vs strict Safaricom `2547XXXXXXXX` |
| 5 | Flexible login (phone / ID / email) | High | **Missing** — auth still email-only |
| — | Live `DARAJA_None` | Critical | **Provider reject** — separate from phone format; credentials/callback/body |

---

## 1. Strong password policy (beyond length)

### Current behaviour
- `AuthService.register` / `change_password` hash and store; no complexity rules in service layer.
- Client may enforce UI rules; **server does not**.

### Required backend work
1. Add `app/core/password_policy.py` (or equivalent):
   - Min length ≥ 10 (or product choice)
   - At least one upper, lower, digit, symbol
   - Reject common passwords / sequential patterns
   - Reject password == email / phone
2. Call policy on:
   - `register`
   - `change_password`
   - any future OTP set-password
3. Return stable error code, e.g. `PASSWORD_POLICY_VIOLATION`, with safe message list.

### Out of scope
- Frontend checklist only (must mirror server, not replace it).

---

## 2. Server-side enforce `must_change_password`

### Current behaviour
- Column `users.must_change_password` exists.
- Token / `/me` expose the flag.
- `change_password` clears flag and revokes refresh tokens.
- **No FastAPI dependency** rejects other authenticated routes when flag is true.
- Frontend AppShell gates UI only → API still fully usable with old password.

### Required backend work
1. Dependency `require_password_changed` (or extend `get_current_user`):
   - If `user.must_change_password` and path is **not** in allowlist → `403` with code `PASSWORD_CHANGE_REQUIRED`.
2. Allowlist:
   - `POST /auth/change-password`
   - `POST /auth/logout` (or revoke refresh)
   - `GET /auth/me` (optional, so UI can read flag)
3. Do **not** allow chama/payment/admin routes until cleared.
4. Platform `require_password_change` admin action already sets the flag — keep it.

### Acceptance
- User with flag=true cannot `POST .../payment-intents` or list chamas until password changed.
- After `change_password`, full access resumes.

---

## 3. Chair payment success but no shares — settlement root cause

### Current behaviour (code)

`settle_linked_contribution` (**ADR-019**):

```text
if payment_intent.contribution_id is None:
    return False   # NO contribution confirm, NO share, NO ledger
