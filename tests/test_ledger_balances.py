"""Read-only ledger account balances and per-account entries (brief 4.2)."""

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models.ledger_account import LedgerAccount
from app.models.user import User
from app.services.ledger import LedgerLine, LedgerService
from tests.conftest import register_and_login


def _account(db, chama_id, code):
    return db.scalars(
        select(LedgerAccount).where(
            LedgerAccount.chama_id == chama_id, LedgerAccount.code == code
        )
    ).one()


def _get_user(db, email):
    return db.scalars(select(User).where(User.email == email)).one()


def _setup(client, db, email="accounts@example.com", phone="+254700000301", govt="GID-301"):
    from tests.conftest import create_chama

    headers = register_and_login(client, email)
    chama = create_chama(client, headers, name="Balances Chama", phone=phone, govt=govt)
    chama_id = uuid.UUID(chama["id"])
    cash = _account(db, chama_id, "1000")
    equity = _account(db, chama_id, "3000")
    return headers, chama_id, cash, equity


def _post(client, db, headers, chama_id, cash, equity, *, amount="100.00", description="t"):
    actor = _get_user(db, "accounts@example.com")
    LedgerService(db).post_transaction(
        actor=actor,
        chama_id=chama_id,
        source_type="TEST",
        source_id=uuid.uuid4(),
        description=description,
        lines=[
            LedgerLine(account_id=cash.id, debit=Decimal(amount)),
            LedgerLine(account_id=equity.id, credit=Decimal(amount)),
        ],
    )


def test_account_balances_computed_from_entries(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    _post(client, db, headers, chama_id, cash, equity, amount="100.00", description="t1")
    _post(client, db, headers, chama_id, cash, equity, amount="50.00", description="t2")

    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200
    by_code = {item["code"]: item for item in r.json()["items"]}
    assert set(by_code) == {"1000", "3000", "4000", "1100", "5000"}
    assert by_code["1000"]["balance"] == "150.00"
    assert by_code["3000"]["balance"] == "-150.00"
    assert by_code["4000"]["balance"] == "0.00"
    assert by_code["1100"]["balance"] == "0.00"
    assert by_code["5000"]["balance"] == "0.00"
    assert isinstance(by_code["1000"]["balance"], str)


def test_balances_zero_when_no_postings(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200
    assert all(item["balance"] == "0.00" for item in r.json()["items"])


def test_account_entries_endpoint_paginates(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    for i in range(3):
        _post(client, db, headers, chama_id, cash, equity, amount="10.00", description=f"t{i}")

    r = client.get(
        f"/api/v1/chamas/{chama_id}/ledger/accounts/{cash.id}/entries?limit=2",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["code"] == "1000"
    assert body["account"]["balance"] == "30.00"
    assert len(body["items"]) == 2
    assert body["has_more"] is True
    assert body["next_cursor"]

    r2 = client.get(
        f"/api/v1/chamas/{chama_id}/ledger/accounts/{cash.id}/entries"
        f"?limit=2&cursor={body['next_cursor']}",
        headers=headers,
    )
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False
    entry = body2["items"][0]
    assert entry["debit"] == "10.00"
    assert entry["credit"] == "0.00"
    assert entry["source_type"] == "TEST"

    seen = [e["id"] for e in body["items"] + body2["items"]]
    assert len(set(seen)) == 3
    descriptions = {e["description"] for e in body["items"] + body2["items"]}
    assert descriptions == {"t0", "t1", "t2"}


def test_account_entries_reject_cross_chama_account(client, db):
    headers_a, chama_a, cash_a, _ = _setup(
        client, db, email="a@example.com", phone="+254700000302", govt="GID-302"
    )
    headers_b, chama_b, _, _ = _setup(
        client, db, email="b@example.com", phone="+254700000303", govt="GID-303"
    )
    r = client.get(
        f"/api/v1/chamas/{chama_b}/ledger/accounts/{cash_a.id}/entries",
        headers=headers_b,
    )
    assert r.status_code == 400


def test_balances_require_membership(client, db):
    headers, chama_id, _, _ = _setup(client, db)
    headers_stranger = register_and_login(client, email="stranger@example.com")
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers_stranger)
    assert r.status_code == 403


def test_balances_require_auth(client, db):
    r = client.get(f"/api/v1/chamas/{uuid.uuid4()}/ledger/accounts")
    assert r.status_code == 401