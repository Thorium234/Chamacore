# Business Rules

Only rules marked `APPROVED` may be implemented.

## Approved rules

### Member and membership

- A Member represents a person.
- A Membership represents participation in one Chama.
- Contributions and shares reference Membership.
- Membership numbers are generated server-side.
- Membership numbers must not use `COUNT(*) + 1`.
- Membership numbers are unique within a Chama (`UNIQUE(chama_id, membership_number)`).
- A person cannot have duplicate membership in one Chama (`UNIQUE(chama_id, member_id)`).
- Membership numbers are allocated transactionally using a sequence table.

### Money

- Monetary values cannot be negative.
- Monetary values use `Decimal`.
- Database monetary columns use `NUMERIC`.
- Confirmed financial records cannot be silently deleted.

### Identity (ADR-007)

- Both `phone_number` and `government_id` are globally unique on the `members` table.
- Duplicate phone or government ID is rejected at creation time.

### User-to-member linking (ADR-008 addendum, OQ-008)

- A user not yet linked to a member may claim their identity by matching a
  member's `phone_number` and `government_id` through
  `POST /api/v1/auth/me/member-link`.
- A user already linked to a member cannot claim again.

### Chama access (ADR-008)

- The creator of a Chama is automatically added as a member with `CHAIRPERSON` role.
- Authorization requires an active membership in the Chama.

### Registration fees (ADR-003)

- Registration fee is copied from the Chama at membership creation as an obligation (`OWED`).
- Fee statuses are `OWED` or `WAIVED`.
- Registration fee rows are never physically deleted.

### Contributions (ADR-004, ADR-009)

- Contribution period is a calendar month in `YYYY-MM` format.
- Statuses are `PENDING`, `CONFIRMED`, `REVERSED`.
- Only `CHAIRPERSON` or `TREASURER` may record contributions.
- Only `CHAIRPERSON` may confirm or reverse contributions.
- `CONFIRMED` contributions are immutable in amount and period.
- Correction is recorded by changing status to `REVERSED` with an optional note.
- A membership may have at most one non-reversed contribution per period.
- Contribution rows are never physically deleted.

### Shares (ADR-005)

- Each confirmed contribution creates one share record.
- `units = amount / SHARE_UNIT_PRICE` (default KES 100).
- Shares are created automatically when a contribution is confirmed.
- Fractional units are permitted.
- Share records are never physically deleted.

### Roles (ADR-006)

- Four roles: `CHAIRPERSON`, `TREASURER`, `SECRETARY`, `MEMBER`.
- Every membership automatically receives `MEMBER`.
- `MEMBER` cannot be assigned or removed through the role API.
- A membership may hold at most one leadership role (`CHAIRPERSON`, `TREASURER`, or `SECRETARY`).
- A Chama may have at most one `CHAIRPERSON`.
- Only `CHAIRPERSON` may assign or remove leadership roles.
- `TREASURER` and `SECRETARY` have no role-assignment powers.
- `CHAIRPERSON` may confirm or reverse contributions.
- `CHAIRPERSON` or `TREASURER` may record contributions.
- `CHAIRPERSON` may waive registration fees.
- `CHAIRPERSON`, `TREASURER`, or `SECRETARY` may create memberships.
- Only `CHAIRPERSON` may update Chama details or Chama status.
- Only `CHAIRPERSON` may update a membership's status.
