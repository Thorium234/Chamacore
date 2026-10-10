# Data Retention & Account Deletion Policy

**Applies to:** ChamaCore Backend, Identity, Ledger, and Compliance  
**Governing Standard:** Kenya Data Protection Act (KDPA) 2019 & Financial Regulatory Retention Rules  
**Core Invariant:** User-initiated account deletion triggers a **retention policy state machine**, never a hard delete of financial ledger records or historical audit entries.

---

## 1. Account Deletion Lifecycle & State Machine

When a user triggers "Delete my account" via `POST /api/v1/auth/delete-account` (with password confirmation):

```
[ Active User ]
       │
       ▼ (User verifies password & triggers deletion)
[ Deactivated (is_active = False) ]
  ├── 1. Revoke all active refresh tokens immediately
  ├── 2. Reject future logins (401)
  ├── 3. Reject active JWT access tokens (deps.py checks user.is_active -> 401)
  ├── 4. Record append-only business audit event: `auth.account_delete`
  └── 5. Retain immutable ledger records, shares, and contributions
       │
       ▼ (Grace period / retention window expiration)
[ Anonymized / Redacted ]
  ├── Erase personal identifiers (email, phone, national ID)
  └── Preserve anonymous membership and ledger transaction references
```

---

## 2. Data Retention Schedule by Category

| Data Class | Specific Fields & Tables | Retention Duration | Post-Retention Action | Regulatory / Operational Rationale |
|---|---|---|---|---|
| **Authentication Credentials** | `users.password_hash`, `refresh_tokens.*` | 0–14 days grace | Destroyed permanently | Minimizes credential attack surface; tokens revoked immediately on deletion. |
| **Identity & KYC PII** | `members.first_name`, `last_name`, `phone_number`, `government_id`, `users.email` | 7 years from membership termination | Anonymized (e.g. `ANON_USER_uuid`) or deleted | Required under Kenyan AML / Financial Reporting regulations for auditability of transactions. |
| **Financial Ledger** | `ledger_transactions`, `ledger_entries`, `ledger_accounts` | Permanent (Indefinite) | Retained permanently | Double-entry ledger integrity; historical financial statements and group balance reconciliation must never break. |
| **Contributions & Shares** | `contributions`, `shares` | Permanent (Indefinite) | Retained permanently | Proves ownership history and capital allocation for group members. |
| **Payment Provider References** | `payment_intents`, `payment_attempts`, `provider_transactions`, Daraja receipts | 7 years | Retained permanently or archived | Proof of transaction reconciliation with Safaricom / Daraja in case of dispute. |
| **Business Audit Logs** | `audit_events` | 7 years | Retained append-only; immutable | Required for accountability, security audits, and regulatory compliance. |
| **In-App Notifications** | `notifications` | 90 days | Deleted | Ephemeral operational delivery records. |

---

## 3. Operational Guarantees

1. **No Orphan Active Logins:** Immediately upon processing account deletion, all sessions are terminated. Even if an access token has not yet hit its expiration time, API dependency validation rejects the call because `user.is_active == False`.
2. **Platform Admin Safety:** The last active platform administrator cannot self-delete their account, preventing governance lockout.
3. **Foreign Key Integrity:** Database foreign keys (`RESTRICT` / `NO ACTION`) prevent cascading deletion of financial rows attached to member accounts.
