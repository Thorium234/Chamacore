# ADR-026: Authentication & Multi-Session Security Hardening

## Status
Accepted

## Context
ChamaCore manages real group financial assets. Long-lived access credentials or persistent sessions that survive password changes or credential compromise introduce unacceptable attack vectors. At the same time, forcing frequent full credentials logins degrades user experience.

## Decision
1. **Short-Lived Access Tokens:** Access tokens have a default lifetime of 120 minutes (`CHAMACORE_JWT_EXPIRES_MINUTES = 120`), carrying minimal payload (subject user ID, expiry).
2. **Rotating Single-Use Refresh Tokens:** Refresh tokens are opaque, high-entropy tokens whose SHA-256 digests are stored in the database. Every refresh request rotates the token: the presented token is revoked and a single new replacement is issued.
3. **Multi-Session Revocation on Password Change:** Calling `/api/v1/auth/change-password` revokes all active refresh tokens for the user in the same database transaction. Any other device or session attempting to refresh its token is immediately rejected with HTTP 401.
4. **Session Verification on Every Authenticated Request:** `get_current_user` in `app/api/deps.py` queries `user.is_active` on each request, ensuring deactivated or deleted accounts lose access immediately even before their JWT access token expires.

## Consequences & Failure Modes
- Other devices logged into the same account will be logged out upon password change when their access tokens expire or when they attempt a refresh.
- A stolen refresh token cannot be used repeatedly because using it immediately revokes it and its chain.
