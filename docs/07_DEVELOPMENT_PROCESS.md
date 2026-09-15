# Development Process

For every feature:

1. Confirm it is in the active roadmap version.
2. Read the relevant domain and business rules.
3. Check for open decisions.
4. Define or update the database design.
5. Define the API contract.
6. Implement the model.
7. Create an Alembic migration.
8. Implement the service.
9. Implement the endpoint.
10. Add tests.
11. Run formatting and tests.
12. Update documentation and project status.

## Definition of done

A feature is complete only when:

- Its business rule is approved.
- Its model and migration exist.
- The migration works from a clean database.
- Its API contract is documented.
- Authorization and error cases are tested.
- The happy path is tested.
- Documentation matches code.
- Project status is updated.

## Required commands

The completed project should support:

```bash
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

These commands must work from a clean checkout.