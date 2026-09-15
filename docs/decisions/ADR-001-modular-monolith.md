# ADR-001: Use a Modular Monolith

## Status

Accepted

## Decision

ChamaCore will begin as one FastAPI application with modular internal
boundaries and one primary relational database.

## Reason

The product is early, the domain is still being validated, and distributed
infrastructure would add operational complexity before it is justified.

## Consequences

- Modules must have clear boundaries.
- Provider integrations must remain behind interfaces.
- The architecture can be split later if real scale or ownership needs
  justify it.