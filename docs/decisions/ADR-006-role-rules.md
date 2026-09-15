# ADR-006: Role Rules and Permissions

## Status

Approved

## Decision

### Roles

There are four roles: `CHAIRPERSON`, `TREASURER`, `SECRETARY`, `MEMBER`.

### Default role

Every membership automatically receives the `MEMBER` role at creation.

### Leadership roles

A membership may hold at most one leadership role (`CHAIRPERSON`,
`TREASURER`, or `SECRETARY`) in addition to the default `MEMBER` role.

A Chama may have at most one `CHAIRPERSON` at a time.

### Permissions

- The `MEMBER` role is assigned automatically when a membership is created.
  It cannot be assigned or removed through the role API.
- Role assignment and removal therefore apply to leadership roles
  (`CHAIRPERSON`, `TREASURER`, `SECRETARY`) and are restricted to the
  `CHAIRPERSON` role.
- `CHAIRPERSON` may assign and remove leadership roles on any membership
  in their Chama.
- `TREASURER` and `SECRETARY` have no role-assignment powers; their
  authority is limited to registering members (auto-granting `MEMBER`).
- Only the `CHAIRPERSON` may confirm or reverse contributions.
- Only the `CHAIRPERSON` or `TREASURER` may record contributions.
- Only the `CHAIRPERSON` may waive registration fees.
- `CHAIRPERSON`, `TREASURER`, or `SECRETARY` may create memberships
  (register members).
- Only the `CHAIRPERSON` may update Chama details or change Chama status.
- Only the `CHAIRPERSON` may update a membership's status (activate or
  deactivate a member).

### Ownership

The user who creates a Chama is automatically added as a member with
`CHAIRPERSON` (and `MEMBER`) roles on that Chama.

## Reason

This provides a realistic permission model for a Kenyan chama while keeping
V1 simple. The chairperson role mirrors real-world chama governance.

## Consequences

- The system must enforce a single chairperson per Chama.
- The system must enforce at most one leadership role per membership.
- Role assignment and removal require chairperson authorization.
- The `MEMBER` role is implicitly present and cannot be removed from a
  membership.
