# Business Rules

Only rules marked `APPROVED` may be implemented. Rules marked `OPEN` must not
be guessed.

## Approved rules

### Member and membership

- A Member represents a person.
- A Membership represents participation in one Chama.
- Contributions and shares reference Membership.
- Membership numbers are generated server-side.
- Membership numbers must not use `COUNT(*) + 1`.

### Money

- Monetary values cannot be negative.
- Monetary values use `Decimal`.
- Database monetary columns use `NUMERIC`.
- Confirmed financial records cannot be silently deleted.

## Open decisions

### Registration fees

- Is the fee copied from the Chama when membership is created?
- Can it change after creation?
- Is it an amount owed, a manual record, or a confirmed payment?
- Can it be waived?

### Contributions

- Can a membership make multiple contributions in one period?
- What defines a contribution period?
- Who can confirm a contribution?
- Can a confirmed contribution be corrected?
- What statuses are allowed?

### Shares

- What formula converts a contribution into shares?
- Are shares created automatically?
- Can one contribution create multiple share records?
- What happens when a contribution is reversed?

### Roles

- Can one membership have multiple roles?
- Can a Chama have multiple chairpersons?
- Who may assign or remove roles?
- Is `MEMBER` explicit or a default?

### Identity

- Is a phone number globally unique?
- Is a government ID globally unique?
- Can one person belong to multiple Chamas?
- How is an existing person found during registration?

## Implementation rule

No model, service, endpoint, or migration may depend on an `OPEN` decision.
Resolve each item in an ADR, then move it into the approved section.