# Product Requirements

## Product

ChamaCore manages Kenyan Chamas, their members, memberships, contributions,
shares, and eventually their wider financial activity.

## V1 goal

An authorized user must be able to create a Chama, register members, assign
roles, record registration fees and contributions, and calculate shares using
an approved rule.

## V1 users

- Chama administrator
- Chairperson
- Treasurer
- Secretary
- Ordinary member

## V1 features

### Chama management

- Create a Chama
- View Chama details
- Update Chama details
- Activate or deactivate a Chama

### Member and membership management

- Create a member identity
- Store name, phone number, and government ID/passport number
- Add a member to a Chama
- Generate a server-side membership number
- View and update membership status
- Prevent duplicate membership in one Chama

### Roles

- Assign roles to memberships
- Remove roles according to approved permissions
- Enforce role permissions

### Registration fees

- Record the registration-fee obligation
- Record its status
- Preserve its history

### Contributions

- Record a contribution against a membership
- Store amount, date, period, and status
- Reject invalid amounts
- Prevent invalid duplicates

### Shares

- Calculate shares using the approved formula
- Link shares to the membership and contribution
- Preserve historical share records

## V1 exclusions

V1 excludes loans, payouts, ledger, external payments, M-Pesa, banks,
reconciliation, notifications, web, mobile, and USSD.

## V1 acceptance criteria

V1 is complete only when:

- A Chama can be created through the API.
- A member and membership can be created.
- Membership numbers are safe under concurrency.
- Roles can be assigned securely.
- Unauthorized users cannot access another Chama's data.
- Contributions can be recorded.
- Shares follow documented rules.
- Migrations work from a clean checkout.
- Automated tests pass.