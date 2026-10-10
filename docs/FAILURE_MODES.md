# ChamaCore Failure Modes & Disaster Recovery Catalog

**Audience:** Site reliability engineers (SRE), backend operators, on-call developers  
**Purpose:** Enumerates known systemic failure modes, their user impact, automated mitigations, and runbook remediation steps.

---

## 1. System Failure Matrix

| Failure Mode | User Impact | System Behavior | Operator Remediation |
|---|---|---|---|
| **Database Unavailable / Crashed** | API returns 500/503 errors; users unable to load dashboards or perform writes. | Connection pool throws `OperationalError`; requests fail fast with structured error responses. No partial or corrupt transactions written. | Check database container / host status; inspect connection pool limits (`pool_size`, `max_overflow`); restart PostgreSQL service if necessary. |
| **API Rate Limit Exceeded** | User receives `429 Too Many Requests`. | In-process rate limiter blocks client IP based on bucket threshold; logs warning with client host. | If legitimate spike, increase `CHAMACORE_GENERAL_API_PER_MINUTE_LIMIT` in environment. If malicious, block IP at reverse proxy / Cloudflare level. |
| **Safaricom Daraja API Down / Degraded** | STK Push prompts fail to pop up on user phones; "Payment provider temporarily unavailable". | Daraja adapter maps network/HTTP 5xx errors to retryable or terminal provider codes. Transaction state machine moves intent to `FAILED` or retries. | Check Safaricom Daraja service status page; verify auth token endpoint; notify users via banner; defer automated payment retries. |
| **Webhook Delivery Failure / Unreachable URL** | Payment completes on M-Pesa, but application dashboard does not reflect settlement immediately. | Payment attempt remains in `SUBMITTED` state. Webhooks fail at provider gateway. | Verify public reverse proxy / SSL certificates; run `scripts/reconcile_payment_events.py` or trigger manual payment intent status query via API. |
| **Concurrent Ledger Postings on Same Source** | One concurrent request succeeds; parallel conflicting request receives `409 Conflict`. | Unique database index and optimistic locking prevent double-posting or double-credit of funds. | Idempotency layer handles duplicate requests transparently; client can safely retry on transient network errors. |
| **Session Revocation on Password Change** | User on other device gets 401 on next background token refresh. | Refresh token is rejected; client redirects to `/login` with clean state. | Expected security behavior. Instruct user to sign in with new credentials. |
| **Account Deactivation / Deletion** | Deactivated user attempts to access API; receives 401 Unauthorized. | `deps.py` immediately rejects access token (`user.is_active == False`); all refresh tokens revoked. | Support checks audit event log (`auth.account_delete` or `platform.user_deactivated`) to verify whether deletion was user-initiated or admin-initiated. |

---

## 2. Recovery Procedures for Critical Incidents

### 2.1 Reconciling Unsettled Succeeded Payments
If Daraja processed payments while the webhook server was briefly down:
1. Extract list of unsettled payment intents:
   ```sql
   SELECT id, member_id, amount, created_at 
   FROM payment_intents 
   WHERE state = 'SUBMITTED' AND created_at > NOW() - INTERVAL '24 HOURS';
   ```
2. Run the reconciliation script:
   ```bash
   python scripts/reconcile_payment_events.py
   ```
3. Verify that settled contributions were created and balanced ledger transactions posted.

### 2.2 Unbalanced Ledger Emergency Response
The double-entry ledger is hardened with database check constraints and triggers. If an operational script or bug attempts to commit an unbalanced transaction:
- The transaction rollback will abort the entire database operation.
- Search logs for `UnbalancedTransactionError` or constraint violations.
- Never write direct SQL `INSERT` statements into `ledger_entries` without balanced lines.
