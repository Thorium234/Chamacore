"""Shared test fixtures: in-process SQLite DB, seeded roles, TestClient, auth helpers."""

import os

os.environ.setdefault("CHAMACORE_DEBUG", "true")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.deps import oauth2_scheme
from app.db.base import Base
from app.db.ledger_guards import create_ledger_guards
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.enums import RoleName
from app.models.role import Role

# import all models so Base.metadata is populated
import app.models  # noqa: F401


def _seed_roles(session):
    from sqlalchemy import select

    existing = {name for name, in session.execute(select(Role.name)).all()}
    for role in RoleName:
        if role.value not in existing:
            session.add(Role(name=role.value))
    session.commit()


TEST_DATABASE_URL = os.environ.get("CHAMACORE_DATABASE_URL")


@pytest.fixture()
def db(tmp_path):
    """Yield a fresh DB session backed by a per-test SQLite or a shared PostgreSQL."""
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            create_ledger_guards(conn)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        _seed_roles(session)
        yield session
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
    else:
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

        def _enable_sqlite_constraints(conn, _record):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

        event.listen(engine, "connect", _enable_sqlite_constraints)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            create_ledger_guards(conn)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        _seed_roles(session)
        yield session
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    """Yield a TestClient whose DB dependency is overridden with *db*."""

    def _override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    from fastapi.testclient import TestClient

    try:
        with TestClient(fastapi_app) as c:
            yield c
    finally:
        fastapi_app.dependency_overrides.clear()


def get_concurrency_engine(tmp_path):
    """Engine for concurrency tests: PostgreSQL when CHAMACORE_DATABASE_URL is set, else SQLite WAL."""
    if TEST_DATABASE_URL:
        return create_engine(TEST_DATABASE_URL)
    db_path = tmp_path / "concurrent.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    def _enable_sqlite_constraints(conn, _record):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "connect", _enable_sqlite_constraints)
    return engine


def register_and_login(client, email: str = "user@example.com", password: str = "secret123") -> dict:
    """Register a user and return the auth header dict."""
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, f"register failed: {r.json()}"
    r = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def create_chama(client, headers: dict, *, name: str = "Test Chama", fee: str = "100.00", phone: str = "+254700000001", govt: str = "GID-001") -> dict:
    r = client.post(
        "/api/v1/chamas",
        headers=headers,
        json={
            "name": name,
            "registration_fee_amount": fee,
            "member": {"first_name": "Alice", "last_name": "Wanjiku", "phone_number": phone, "government_id": govt},
        },
    )
    assert r.status_code == 201, f"create_chama failed: {r.status_code} {r.json()}"
    return r.json()


def add_membership(client, headers, chama_id: str, *, phone: str = "+254700000099", govt: str = "GID-099", first: str = "Bob", last: str = "Otieno") -> dict:
    r = client.post(
        f"/api/v1/chamas/{chama_id}/memberships",
        headers=headers,
        json={"member": {"first_name": first, "last_name": last, "phone_number": phone, "government_id": govt}},
    )
    assert r.status_code == 201, f"add_membership failed: {r.status_code} {r.json()}"
    return r.json()