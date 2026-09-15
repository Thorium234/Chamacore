# Architecture

## Style

ChamaCore is a modular monolith: one FastAPI application and one primary
database during the initial versions.

## Layers

```text
API
↓
Pydantic schemas
↓
Application services
↓
Repositories
↓
SQLAlchemy models
↓
Database
```

## Recommended structure

```text
app/
├── main.py
├── core/
│   ├── config.py
│   └── security.py
├── db/
│   ├── base.py
│   └── session.py
├── models/
├── schemas/
├── repositories/
├── services/
└── api/

tests/
alembic/
```

## Rules

- Endpoints handle HTTP concerns.
- Schemas validate external input and output.
- Services contain business operations.
- Repositories contain database access.
- Models represent persistence.
- Authorization runs before returning Chama-scoped data.
- SQLAlchemy models are not returned directly from endpoints.

## Future payment architecture

Payment providers will be adapters behind an internal interface:

```text
Payment Service
  ↓
Payment Provider Interface
  ├── Jenga Adapter
  ├── Daraja Adapter
  ├── KCB BUNI Adapter
  └── NCBA Adapter
```

Do not implement this during V1.