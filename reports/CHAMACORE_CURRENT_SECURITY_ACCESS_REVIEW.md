# ChamaCore Current-State Security and Access-Control Review

**Review date:** 4 November 2026\
**Repository:** `Thorium234/Chamacore`\
**Branch:** `main`\
**Review type:** Remote source inspection. This is not a penetration
test, a local execution of the test suite, or a review of the deployed
environment.

## Executive summary

The current public `main` branch has advanced substantially since the
previous review. The GitHub repository page showed 108 commits at the
time of inspection. The current README describes the V1 foundation, V2
ledger, V3 payments, registration-fee settlement, loans, repayments,
payouts, business audit events, and platform administration as
implemented.

Two reported issues were investigated.

1.  **Logout does not fully terminate the session. Confirmed backend
    weakness.** Login and refresh return access and refresh tokens in
    JSON. The backend does not set authentication cookies. Logout
    revokes the submitted refresh token, but the current access JWT
    remains usable until expiry because authentication does not check a
    session revocation record.
2.  **Admin and ordinary-user dashboards appear mixed. Not verifiable
    from this repository.** The repository is a FastAPI backend and its
    documented scope defers the frontend. There is no browser
    application here to inspect route guards, dashboard selection,
    cookie storage, client-side logout, or navigation. Backend
    platform-admin routes are separated and protected by a global
    `PLATFORM_ADMIN` grant. The frontend source is required to diagnose
    the visual/dashboard issue.

A further issue was identified: platform-admin user deactivation sets
`is_active=False`, but does not revoke all stored refresh tokens. If the
user is later reactivated before those tokens expire, old refresh tokens
may become usable again. This needs a regression test and a targeted
fix.

This review does not establish that the system has been exploited.

## Findings and priority

  --------------------------------------------------------------------------
  ID                Severity          Finding              Evidence status
  ----------------- ----------------- -------------------- -----------------
  AUTH-01           High              Logout revokes       Confirmed
                                      refresh token but    
                                      not the              
                                      already-issued       
                                      access JWT           

  AUTH-02           High              Backend does not set Confirmed
                                      or clear browser     
                                      authentication       
                                      cookies              

  AUTH-03           High              User deactivation    Confirmed design
                                      does not revoke      gap; add
                                      stored refresh       regression test
                                      tokens               

  AUTH-04           Medium            Access tokens have   Confirmed
                                      no server-side       
                                      session/revocation   
                                      check                

  AUTH-05           Medium            Password change      Confirmed
                                      revokes refresh      
                                      tokens but leaves    
                                      current access JWT   
                                      valid until expiry   

  AUTHZ-01          High              Admin/member         Requires frontend
                                      dashboard separation repository
                                      cannot be reviewed   
                                      without frontend     
                                      source               

  AUTHZ-02          Medium            Platform-admin       Hardening
                                      privilege changes    recommendation
                                      need stronger        
                                      assurance and        
                                      explicit security    
                                      tests                

  AUTHZ-03          Medium            Every Chama-scoped   Test requirement
                                      endpoint needs       
                                      cross-Chama          
                                      authorization        
                                      regression coverage  

  DATA-01           Medium            Platform-wide        Confirmed;
                                      responses expose     minimize and
                                      member phone and     audit
                                      account details to   
                                      platform admins      

  OPS-01            Medium            Rate limits are      Documented
                                      process-local and do limitation
                                      not coordinate       
                                      across multiple      
                                      workers              

  OPS-02            Medium            Application          Verify
                                      middleware does not  proxy/frontend
                                      show a Content       layer
                                      Security Policy      

  SCALE-01          Medium            Platform Chama       Confirmed query
                                      listing performs     pattern
                                      per-Chama count      
                                      queries              
  --------------------------------------------------------------------------

Severity is a prioritization judgment, not a claim of exploitation.

------------------------------------------------------------------------

## 1. AUTH-01: Logout does not immediately invalidate access tokens

### Current behavior

The login endpoint creates an access JWT and a refresh token and returns
both in a JSON response. The logout endpoint accepts a refresh token in
the request body and revokes that refresh token.

The current-user dependency validates the access JWT, extracts the user
ID, loads the user, and checks whether the account is active. It does
not check whether the token belongs to a revoked session.

Therefore, logout prevents refresh-token reuse but does not immediately
stop a previously issued access JWT from accessing protected endpoints.
The configured default access-token lifetime is 120 minutes.

### Required change

Implement a deliberate session termination strategy without rewriting
the whole authentication module. The developer should evaluate a
server-side session record, a token/session identifier checked during
authentication, or a per-user token version/security stamp. Document the
selected design.

Distinguish one-device logout from logout-all-devices if both are
required.

### Acceptance criteria

-   After logout succeeds, the logged-out session cannot access
    protected endpoints.
-   The old access token is rejected, not merely allowed to expire.
-   The old refresh token is rejected.
-   Refresh-token replay remains rejected.
-   Logging out one device does not terminate other devices unless
    requested.
-   A logout-all-sessions operation can terminate every active session.
-   Automated tests prove access-token rejection after logout.

------------------------------------------------------------------------

## 2. AUTH-02: Cookie cleanup is not implemented by this backend

### Current behavior

The login and refresh endpoints return tokens as JSON fields. They do
not set `Set-Cookie` headers. The logout endpoint returns HTTP 204 after
revoking a refresh token; it does not expire cookies.

This backend therefore does not own or clear browser authentication
cookies. If the frontend stores credentials in cookies, its current
client-side logout must clear them. If it uses local storage or
in-memory state, the issue is different.

The actual browser storage strategy cannot be established from this
backend repository.

### Required change

Inspect the frontend source and identify whether it uses:

-   HttpOnly cookies
-   JavaScript-readable cookies
-   local storage
-   session storage
-   in-memory state
-   a combination

Choose one consistent strategy. For a browser application, consider
server-set cookies with `HttpOnly`, `Secure`, and appropriate `SameSite`
attributes. If cookie authentication is adopted, implement and test CSRF
defenses. Credentialed CORS is not a CSRF defense.

If cookies are used, logout must expire every application cookie using
matching name, path, and domain attributes, and revoke the corresponding
server-side session/refresh token.

If the project retains bearer tokens in JSON, document that decision and
ensure the frontend clears its storage on logout. Do not claim the
backend clears cookies when it does not.

### Acceptance criteria

-   Inspect browser storage before login, after login, after refresh,
    and after logout.
-   No application authentication cookie or stored token remains after
    logout.
-   The browser cannot refresh the logged-out session.
-   Protected API calls using the old access token fail.
-   Cookie attributes are verified in browser tools and automated tests.
-   If cookies are used, CSRF defenses are tested.
-   Logout works with both a normal and expired access token.

------------------------------------------------------------------------

## 3. AUTH-03: Deactivation does not revoke refresh-token records

### Current behavior

The platform-admin service deactivates a user by setting `is_active` to
false. Authentication rejects inactive users, and refresh checks that
the user is active. However, the deactivation path does not revoke the
user's stored refresh-token records.

If the account is later reactivated while those tokens remain unexpired,
old refresh tokens may become usable again. This is particularly
concerning when deactivation follows suspected account compromise.

### Required change

When an administrator deactivates an account:

-   Revoke every active refresh token for that user.
-   Invalidate existing access sessions.
-   Record who performed the action and when.
-   Capture a reason if the approved product policy supports it.
-   Ensure reactivation never restores old sessions.

Apply the approved session invalidation policy to password resets and
other security-sensitive changes.

### Acceptance criteria

Deactivate a user with multiple sessions. All refresh tokens and access
sessions must fail. Reactivate the user. Old tokens must still fail, and
the user must authenticate again. Add an automated test for this exact
sequence.

------------------------------------------------------------------------

## 4. AUTH-04 and AUTH-05: Session lifetime and password changes

The current access JWT contains a subject and expiry but no session
identifier that the backend checks against a revocation record. Password
change revokes refresh tokens, but the current access token remains
usable until expiry.

That may be acceptable for a normal password change only if explicitly
chosen. It is not sufficient for suspected compromise or an
administrative security reset.

Define the session behavior separately for:

-   User changes their own password.
-   User resets a forgotten password.
-   Administrator forces a password change.
-   Administrator deactivates an account.
-   User logs out of one device.
-   User logs out of all devices.

For compromise-sensitive events, invalidate access sessions as well as
refresh tokens. Do not describe refresh-token revocation as complete
session revocation.

------------------------------------------------------------------------

## 5. AUTHZ-01: Dashboard separation cannot be diagnosed in this backend repository

### What is present

The backend has a distinct platform administration router for platform
statistics, cross-Chama listing, Chama status changes, platform-admin
listing, user search, forced password changes, user
deactivation/reactivation, and platform-admin grants/revocations.

The platform service checks the `PLATFORM_ADMIN` grant before carrying
out these operations. Chama endpoints use authenticated users and Chama
membership authorization. Platform-admin roles are stored separately
from Chama membership roles.

This is a sensible backend distinction.

### What is missing

The reviewed repository does not contain the frontend that renders the
dashboards. The current documented scope defers frontend work.

This review cannot verify:

-   Normal-user dashboard routing.
-   Platform-admin dashboard routing.
-   Frontend route guards.
-   Whether role data is stale or incorrectly cached.
-   Whether admin navigation appears to ordinary users.
-   Whether browser back navigation reveals protected data after logout.
-   Whether the frontend clears cookies or stored tokens.
-   Whether one user's cached data remains after another user signs in.

Do not ask the backend developer to guess at these browser behaviors.
The frontend repository is required.

### Required frontend behavior

Platform administration and Chama membership are separate authorization
contexts.

A platform administrator is not automatically chairperson, treasurer,
secretary, or member of every Chama. A Chama chairperson is not
automatically a platform administrator.

The platform dashboard must contain platform-wide functions. The Chama
dashboard must contain only data and actions authorized for the current
user's active Chama memberships and roles.

Shared visual components may be reused, but route permissions, data
stores, and dashboard state must not leak between contexts.

When a person has both platform-admin privileges and Chama membership,
define a deliberate context switch. Do not merge both permission sets
into one unrestricted dashboard.

The frontend must use server-provided role information, but backend
authorization remains authoritative. Hiding a menu item is not security.

### Acceptance criteria

-   Ordinary user cannot call platform-admin APIs.
-   Chama chairperson without platform-admin grant cannot access
    cross-Chama administration.
-   Platform admin without active membership cannot use member-only
    Chama operations merely because they are an admin.
-   Users holding both roles see distinct contexts with deliberate
    navigation.
-   Direct URL navigation is guarded.
-   Browser back navigation after logout does not reveal protected data.
-   Switching accounts clears previous-user dashboard state and cached
    API responses.
-   A 403 response does not leave privileged data visible.
-   Backend tests prove permissions independently of frontend behavior.

------------------------------------------------------------------------

## 6. AUTHZ-02: Strengthen platform-admin privilege changes

Granting or revoking platform-admin access is high impact. The current
code requires the acting user to already hold `PLATFORM_ADMIN`, which is
necessary. The inspected implementation does not show step-up
authentication or multi-person approval for granting another
administrator.

Decide whether the product requires recent password confirmation, MFA,
notification to existing admins, a reason for every grant/revoke, or a
special last-admin procedure. Do not invent a second-approval policy
without product approval.

Every grant/revoke must be auditable and tested. Unauthorized users must
receive 403. The system must not accidentally remove all viable platform
administrators.

------------------------------------------------------------------------

## 7. AUTHZ-03: Test every Chama-scoped endpoint for cross-Chama access

The shared access helper checks active membership in the requested
Chama. Ledger reads require leadership roles. This is a good foundation,
but a financial application needs comprehensive regression tests.

For every Chama-scoped resource, test:

1.  Anonymous user.
2.  Authenticated user with no Chama membership.
3.  Active ordinary member of the target Chama.
4.  Inactive or suspended member of the target Chama.
5.  Chairperson of the target Chama.
6.  Treasurer of the target Chama.
7.  Secretary of the target Chama.
8.  Active member of another Chama.
9.  Platform administrator without membership in the target Chama.
10. Deactivated user.

Test list and detail endpoints, guessed UUIDs, and update, delete,
approve, reverse, disburse, and payout actions.

A user must never access another Chama's financial records by changing
an ID in a URL or request body.

**Acceptance:** Maintain an endpoint permission matrix and automated
tests for every route. The frontend must never be treated as the
security boundary.

------------------------------------------------------------------------

## 8. DATA-01: Minimize platform-wide personal data exposure

Platform-admin user responses include email, member name, member phone,
and account state. Platform Chama responses include owner email and
phone. These may be operationally necessary, but they are personal data.

Review every field returned by platform-wide endpoints and document why
an administrator needs it. Prefer minimal list responses, separate
detail views for sensitive information, masked phone numbers where full
values are unnecessary, and audit events for sensitive record access. Do
not expose government ID in platform lists. Never place sensitive
information in application logs or error messages.

Do not remove fields blindly if the business needs them. Minimize
deliberately.

------------------------------------------------------------------------

## 9. OPS-01: Rate limiting is process-local

The current rate limiter stores counters in process memory. The
production runbook documents a single-process deployment because rate
limits and metrics are in-memory.

This is not automatically an authentication bypass in a single-process
deployment. It becomes a weakness if the service is scaled across
workers or instances, because each process has a separate counter.

Do not add Redis for appearance. Before horizontal scaling, move rate
limits to a shared store or enforce suitable limits at a trusted
gateway. Verify proxy configuration so client IP addresses cannot be
spoofed through untrusted forwarded headers.

**Acceptance:** Limits remain effective across all production instances.

------------------------------------------------------------------------

## 10. OPS-02: Review production browser security headers

The production middleware sets content-type protection, referrer policy,
frame denial, permissions policy, and HSTS. A Content Security Policy is
not visible in the inspected application middleware. It may be set by a
reverse proxy or frontend host, but that could not be verified here.

Review complete deployed response headers for frontend and API. Set a
suitable Content Security Policy at the layer serving the browser
application. Test it against the real frontend scripts, styles, API
calls, and payment redirects. Also verify TLS, HSTS readiness, exact
production CORS origins, cookie attributes, and error responses.

------------------------------------------------------------------------

## 11. SCALE-01: Platform Chama listing has an N+1 query pattern

The platform service calculates membership counts separately while
preparing each Chama response. This creates additional database round
trips as the number of Chamas grows.

Keep the current response contract and service boundary. Retrieve counts
efficiently using aggregation or a joined query. Add a sensible default
pagination limit. Do not rewrite the platform module.

**Acceptance:** Response behavior remains equivalent and query count
does not grow linearly with returned Chamas. Measure using realistic
data volume.

------------------------------------------------------------------------

## 12. Additional checks before production

### Authentication and identity

-   Verify member identity claiming resists account takeover.
-   Test brute-force and account-enumeration behavior.
-   Verify rate limits behind the actual reverse proxy.
-   Confirm password policy applies consistently to registration,
    change, reset, and bootstrap accounts.
-   Confirm password resets and forced changes invalidate the intended
    sessions.
-   Confirm inactive users cannot refresh or use existing access tokens.
-   Confirm platform-admin bootstrap secrets are removed after
    provisioning.

### Payments and webhooks

-   Verify provider callback authenticity and signature/token
    validation.
-   Test replayed callbacks and duplicate provider transaction IDs.
-   Test callback delivery out of order.
-   Test oversized callback bodies.
-   Test provider timeout and retry behavior.
-   Verify provider credentials never appear in API responses, logs, or
    audit payloads.
-   Verify callbacks cannot settle contributions belonging to another
    Chama or membership.
-   Verify pending or failed payments cannot be represented as settled.
-   Verify production callback URLs use HTTPS.

### Financial integrity

-   Test concurrent loan disbursement and payout completion against
    PostgreSQL.
-   Test duplicate repayments and payout completion.
-   Test reversal authorization and idempotency.
-   Verify ordinary endpoints cannot write directly to the ledger.
-   Verify users cannot access ledger accounts belonging to another
    Chama.
-   Verify financial history remains immutable.

### Data and deployment

-   Verify production database backups and restoration.
-   Verify migration forward-recovery procedures.
-   Verify database credentials use least privilege.
-   Verify secrets are absent from Git history and CI logs.
-   Verify CORS and trusted proxy settings.
-   Verify logs do not contain passwords, tokens, government IDs, or
    provider secrets.

------------------------------------------------------------------------

## 13. Recommended implementation order

### P0: Session termination

1.  Decide and document the session-revocation design.
2.  Make logout invalidate the current access session.
3.  Revoke all refresh tokens when an account is deactivated.
4.  Ensure reactivation cannot revive old sessions.
5.  Define password-change and security-reset session behavior.
6.  Add regression tests.

### P0: Browser credentials

1.  Inspect the frontend repository.
2.  Identify cookie, local storage, session storage, or in-memory
    handling.
3.  Make login, refresh, and logout use one consistent strategy.
4.  Clear all browser credentials on logout.
5.  Add browser-level tests.
6.  If cookies are used, implement CSRF defenses and verify cookie
    attributes.

### P0: Dashboard separation

1.  Inspect frontend route guards and role resolution.
2.  Keep platform-admin and Chama roles separate.
3.  Separate platform-wide data from Chama-scoped data.
4.  Clear cached user data on logout and account switching.
5.  Test direct URL access and API access independently.

### P1: Authorization and privacy

1.  Build the endpoint permission matrix.
2.  Test cross-Chama access for every resource.
3.  Review platform-admin grant/revoke security.
4.  Minimize platform-wide personal data.
5.  Audit sensitive administrative reads and writes.

### P1: Production and scale

1.  Verify production headers and proxy configuration.
2.  Prepare shared rate limiting before horizontal scaling.
3.  Fix the Chama-list N+1 query pattern.
4.  Add realistic load tests.
5.  Verify backup and restore procedures.

------------------------------------------------------------------------

## 14. Required regression scenarios

  -----------------------------------------------------------------------
  Scenario                            Expected result
  ----------------------------------- -----------------------------------
  Login, logout, then use old access  Rejected
  token                               

  Login, logout, then refresh old     Rejected
  refresh token                       

  Deactivate user with multiple       All sessions invalidated
  sessions                            

  Reactivate previously deactivated   Old tokens remain invalid
  user                                

  Change password                     Existing sessions follow the
                                      approved revocation policy

  Ordinary user calls platform stats  403

  Ordinary user lists platform Chamas 403

  Chama chair calls platform user     403 unless separately granted
  search                              platform-admin

  Platform admin without Chama        403
  membership reads Chama ledger       

  Member of Chama A requests Chama B  403
  ledger                              

  User changes resource UUID to       No unauthorized data returned
  another member's resource           

  User logs out and presses browser   Protected content unavailable
  back                                

  User A logs out and User B logs in  No User A data remains in UI cache
  on same browser                     

  Platform-admin grant is revoked     Privileged API access denied
  while logged in                     immediately

  Account is deactivated while logged Protected API access denied
  in                                  immediately

  Requests are distributed across     Shared rate limit remains effective
  production workers                  

  Large platform Chama list           Query count remains bounded
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 15. Review limitations

This review inspected publicly accessible source files on `main`. It did
not run the application, execute tests, inspect a deployed environment,
or perform a live penetration test.

The following require additional access:

-   Actual frontend source and dashboard routes.
-   Browser cookie attributes and storage behavior.
-   Deployed production configuration and reverse proxy.
-   Live database permissions and production data.
-   Real Daraja sandbox callback behavior.
-   CI results from the latest commit.
-   Whether production deployment matches `main`.

Absence of a finding is not proof that a control is secure.

------------------------------------------------------------------------

## 16. Final developer instruction

Do not refactor the entire system. Start with logout and session
invalidation, because that is the clearest confirmed weakness. Then
inspect the frontend to resolve cookie cleanup and dashboard mixing. The
backend repository does not contain enough evidence to fix those browser
behaviors correctly.

After that, prove the separation between platform administrators, Chama
leaders, and ordinary members with automated authorization tests.
Finally, address privacy, rate limiting, response headers, and query
scaling.

Do not rewrite FastAPI, SQLAlchemy, the ledger, or the modular monolith.
Do not invent frontend behavior. Do not weaken financial controls.
Preserve what works, close confirmed gaps, and prove the fixes with
tests.
