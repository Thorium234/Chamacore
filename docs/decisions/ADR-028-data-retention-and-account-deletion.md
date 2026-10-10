# ADR-028: Data Retention & User-Initiated Account Deletion

## Status
Accepted

## Context
Under the Kenya Data Protection Act (KDPA) 2019, users have a right to request erasure of their personal data. However, as a financial recordkeeping and transaction processing platform, ChamaCore is legally obligated under POCAMLA and financial accounting standards to maintain immutable transaction records and audit trails for a minimum of 7 years. Direct hard-deletion of user records would violate foreign keys and destroy double-entry ledger balance integrity.

## Decision
1. **User Deletion Endpoint:** Implement `POST /api/v1/auth/delete-account` requiring re-entry of the user's current password.
2. **Immediate Access Termination:**
   - Set `user.is_active = False`.
   - Revoke all refresh tokens for the user immediately.
   - Enforce rejection in `get_current_user` so existing JWT access tokens are immediately denied (HTTP 401).
   - Reject subsequent login attempts.
3. **Data Retention Engine:**
   - Retain immutable ledger transactions, entries, contributions, shares, and audit logs.
   - Detach credentials; schedule PII anonymization after regulatory retention periods expire.
4. **Platform Admin Protection:** The last active platform administrator is prevented from self-deleting to protect system governance.

## Consequences & Failure Modes
- Financial records and audit histories remain 100% intact and verifiable.
- User accounts cannot be revived without administrator review.
