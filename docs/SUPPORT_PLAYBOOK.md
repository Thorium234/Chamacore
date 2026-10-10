# ChamaCore Customer & Operations Support Playbook

**Audience:** Customer support engineers, platform operators, on-call engineers  
**Scope:** Payment troubleshooting, authentication escalations, Daraja M-Pesa failures, and account issues.

---

## 1. Incident Severity Definitions

| Severity | Definition | Response Target | Examples |
|---|---|---|---|
| **SEV1 — Critical** | Immediate financial inaccuracy, double-posting to ledger, broad payment settlement outage | < 15 minutes | Users charged twice; STK success not posting to ledger across multiple Chamas; ledger balance corruption. |
| **SEV2 — Major** | Degraded financial operation or integration failure with workaround | < 1 hour | Daraja webhook endpoint unreachable; single Chama payments failing; authentication refresh looping. |
| **SEV3 — Moderate** | Individual user or workflow issue | < 4 hours | One member unable to link identity; single STK prompt timed out; password reset email delayed. |
| **SEV4 — Minor** | Cosmetic UI glitch or documentation clarification | Next business day | Minor translation typo; table pagination alignment; non-critical badge display issue. |

---

## 2. Where to Look (Diagnostic Sources)

1. **Application Logs:** Structured JSON logs containing `request_id`, `actor_id`, and `chama_id`.
   - Production log file or log aggregator (Datadog/CloudWatch/Loki).
2. **Database Tables:**
   - `payment_intents` & `payment_attempts`: Inspect `state`, `provider_code`, and `failure_reason`.
   - `payment_events`: Inspect webhook payloads and idempotency keys (`provider_event_id`).
   - `ledger_transactions` & `ledger_entries`: Verify balanced debits and credits.
   - `audit_events`: Full history of sensitive actions and login events.
3. **Provider Dashboard:** Safaricom Daraja portal (check STK Push logs, C2B callback response codes, and certificate validity).
4. **Environment Variables:** Verify `CHAMACORE_PAYMENT_WEBHOOK_BASE_URL` matches the registered public URL.

---

## 3. Authentication & Access Troubleshooting

| Issue | Root Cause | Operator Resolution |
|---|---|---|
| **Login fails with 401** | Wrong password, unnormalized phone number, or account deactivated | Check `SELECT is_active, must_change_password FROM users WHERE email = ...`. Verify phone normalization (`+254...`). |
| **Forced Password Change loop** | User has `must_change_password=True` | Guide user to complete `/change-password`. If required, platform admin can reset. |
| **403 Forbidden on Chama views** | User not an active member of the selected Chama | Check `memberships` table for `(user_id, chama_id)` and verify status is `ACTIVE`. |
| **Chama Read-Only Error** | Chama is newly created and in `PENDING_APPROVAL` status | A Platform Admin must approve/activate the Chama via `/api/v1/platform/chamas/{id}/status`. |

---

## 4. Double Charge — Investigation Checklist

When a customer reports being charged twice on M-Pesa:

1. **Collect Critical Evidence:**
   - Member phone number (`+254...`)
   - Exact timestamps of charges
   - Amounts deducted
   - Chama name and Chama ID
   - Safaricom M-Pesa SMS confirmation codes (e.g., `NL98ABCDEF`)
2. **Locate Payment Intents:**
   - Query `payment_intents` by member phone and date range.
   - Query `payment_attempts` to check all `CheckoutRequestID` and `MerchantRequestID` values issued.
3. **Check Provider Event Deduplication:**
   - Query `payment_events` for matching `provider_event_id`. ChamaCore's webhook inbox automatically rejects duplicate callback deliveries.
4. **Distinguish Scenarios:**
   - **Scenario A: Customer triggered payment twice (Two separate Safaricom charges).**
     - Two different `CheckoutRequestID`s exist and both succeeded.
     - Review Chama refund policy. If valid, initiate compensating payout reversal through Chama treasurer. **Never directly delete ledger records.**
   - **Scenario B: One Safaricom charge, two ledger postings (Ledger bug).**
     - Safaricom issued one receipt, but multiple ledger transactions reference it.
     - Isolate transaction IDs and apply a compensating reversal transaction via `LedgerService.post_reversal`.
5. **Document Resolution:**
   - Record findings in support ticket with all transaction IDs and update the customer.

---

## 5. Payment Failure Triage (Daraja STK & C2B)

| Symptom | What to Check | Resolution |
|---|---|---|
| **No STK push received on phone** | Phone number format, SIM toolkit response, MSISDN active status | Ensure phone is formatted as `2547XXXXXXXX`. Check if handset is roaming or SIM is blocked. |
| **`DARAJA_INVALID_AUTH`** | Sealed credentials in `payment_connections` | Re-enter consumer key & consumer secret in Chama payment connection settings. |
| **Payment succeeded on M-Pesa but no shares/contribution credited** | Check `payment_intents.settlement_status` | Ensure payment intent has `purpose == 'CONTRIBUTION'`. Run `scripts/reconcile_payment_events.py` to trigger background settlement. |
| **C2B Paybill validation rejected (ResultCode 1)** | `BillRefNumber` not matching active membership number | Inform member to use their exact Chama membership number as the Paybill account number. |
| **Webhook unreachable / callback timeout** | Public URL accessibility | Verify server SSL certificate and ensure webhook endpoint is publicly reachable by Safaricom IP ranges. |

---

## 6. Escalation Protocol & Data Capture

If an issue cannot be resolved through standard triage:

1. **Capture Incident Details:**
   - Chama ID & Name
   - User ID & Member ID
   - Intent ID / Attempt ID
   - `CheckoutRequestID` and M-Pesa Receipt Number
   - Request ID from logs (`X-Request-ID`)
2. **Escalate To:**
   - Financial Core / Ledger Lead: For any ledger discrepancy or unbalanced transaction.
   - Integrations On-Call: For Safaricom API degradation or certificate expiry.
3. **Communication:**
   - Update platform status channel with estimated time to resolution.
