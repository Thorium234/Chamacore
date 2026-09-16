"""V2 ledger tests: posting rules, idempotency, reversal, authorization, scoping."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.enums import LedgerAccountType
from app.models.ledger_account import LedgerAccount
from app.models.ledger_transaction import LedgerTransaction
from app.models.user import User
from app.services.ledger import REVERSAL_SOURCE_TYPE, LedgerLine, LedgerService
from tests.conftest import create_chama, register_and_login


def _add_account(db, chama_id: uuid.UUID, code: str, name: str, account_type: LedgerAccountType):
    account = LedgerAccount(chama_id=chama_id, code=code, name=name, account_type=account_type)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _get_user(db, email: str) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def _post(db, actor: User, chama_id: uuid.UUID, cash_id: uuid.UUID, equity_id: uuid.UUID, *, source_type="TEST"):
    return LedgerService(db).post_transaction(
        actor=actor,
        chama_id=chama_id,
        source_type=source_type,
        source_id=uuid.uuid4(),
        description="test posting",
        lines=[
            LedgerLine(account_id=cash_id, debit=Decimal("100.00")),
            LedgerLine(account_id=equity_id, credit=Decimal("100.00")),
        ],
    )


def _setup(client, db, *, email="user@example.com", phone="+254700000001", govt="GID-001"):
    headers = register_and_login(client, email=email)
    chama = create_chama(client, headers, name="Ledger Chama", phone=phone, govt=govt)
    chama_id = uuid.UUID(chama["id"])
    cash = _add_account(db, chama_id, "1000", "Cash", LedgerAccountType.ASSET)
    equity = _add_account(db, chama_id, "3000", "Contribution Equity", LedgerAccountType.EQUITY)
    return headers, chama_id, cash, equity


def test_post_balanced_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")

    txn = _post(db, actor, chama_id, cash.id, equity.id)

    assert txn is not None
    assert len(txn.entries) == 2
    transactions = LedgerService(db).list_by_chama(actor=actor, chama_id=chama_id)
    assert len(transactions) == 1


def test_get_ledger_endpoint_returns_history(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    _post(db, actor, chama_id, cash.id, equity.id)

    r = client.get(f"/api/v1/chamas/{chama_id}/ledger", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    entry = body[0]["entries"][0]
    assert entry["account_code"] == "1000"
    assert entry["account_name"] == "Cash"
    assert entry["debit"] == "100.00"
    assert entry["credit"] == "0.00"


def test_post_unbalanced_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="unbalanced",
            lines=[
                LedgerLine(account_id=cash.id, debit=Decimal("100.00")),
                LedgerLine(account_id=equity.id, credit=Decimal("90.00")),
            ],
        )
    assert "balance" in str(exc.value).lower()

    assert len(LedgerService(db).list_by_chama(actor=actor, chama_id=chama_id)) == 0


def test_post_zero_or_both_sides_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="no amounts",
            lines=[
                LedgerLine(account_id=cash.id),
                LedgerLine(account_id=equity.id),
            ],
        )
    assert "debit or credit" in str(exc.value)

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="both sides",
            lines=[
                LedgerLine(account_id=cash.id, debit=Decimal("100.00"), credit=Decimal("1.00")),
                LedgerLine(account_id=equity.id, credit=Decimal("101.00")),
            ],
        )
    assert "exactly one of debit or credit" in str(exc.value)


def test_post_negative_amount_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="negative",
            lines=[
                LedgerLine(account_id=cash.id, debit=Decimal("-100.00")),
                LedgerLine(account_id=equity.id, credit=Decimal("-100.00")),
            ],
        )
    assert "cannot be negative" in str(exc.value)


def test_post_account_from_other_chama_rejected(client, db):
    _, chama_a, cash_a, _ = _setup(client, db, email="a@example.com",
                                   phone="+254700000001", govt="GID-001")
    _, chama_b, _, equity_b = _setup(client, db, email="b@example.com",
                                     phone="+254700000002", govt="GID-002")
    actor_b = _get_user(db, "b@example.com")

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor_b,
            chama_id=chama_b,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="cross-chama",
            lines=[
                LedgerLine(account_id=cash_a.id, debit=Decimal("100.00")),
                LedgerLine(account_id=equity_b.id, credit=Decimal("100.00")),
            ],
        )
    assert "does not exist in this Chama" in str(exc.value)


def test_post_unknown_account_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")

    with pytest.raises(Exception) as exc:
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description="missing account",
            lines=[
                LedgerLine(account_id=uuid.uuid4(), debit=Decimal("100.00")),
                LedgerLine(account_id=equity.id, credit=Decimal("100.00")),
            ],
        )
    assert "does not exist in this Chama" in str(exc.value)


def test_idempotent_retry_returns_same_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    service = LedgerService(db)
    source_id = uuid.uuid4()

    first = service.post_transaction(
        actor=actor,
        chama_id=chama_id,
        source_type="CONTRIBUTION",
        source_id=source_id,
        description="first",
        lines=[
            LedgerLine(account_id=cash.id, debit=Decimal("100.00")),
            LedgerLine(account_id=equity.id, credit=Decimal("100.00")),
        ],
    )
    second = service.post_transaction(
        actor=actor,
        chama_id=chama_id,
        source_type="CONTRIBUTION",
        source_id=source_id,
        description="retry",
        lines=[
            LedgerLine(account_id=cash.id, debit=Decimal("100.00")),
            LedgerLine(account_id=equity.id, credit=Decimal("100.00")),
        ],
    )

    assert second.id == first.id
    assert len(LedgerService(db).list_by_chama(actor=actor, chama_id=chama_id)) == 1


def test_reversal_creates_compensating_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    service = LedgerService(db)
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    reversal = service.reverse_transaction(
        actor=actor, chama_id=chama_id, transaction_id=txn.id, description="correction"
    )

    assert reversal.reverses_transaction_id == txn.id
    assert reversal.source_type == REVERSAL_SOURCE_TYPE
    entries_by_account = {e.account_id: e for e in reversal.entries}
    assert entries_by_account[cash.id].credit == Decimal("100.00")
    assert entries_by_account[equity.id].debit == Decimal("100.00")

    all_txns = service.list_by_chama(actor=actor, chama_id=chama_id)
    assert len(all_txns) == 2


def test_double_reversal_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    service = LedgerService(db)
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    service.reverse_transaction(actor=actor, chama_id=chama_id, transaction_id=txn.id)

    with pytest.raises(Exception) as exc:
        service.reverse_transaction(actor=actor, chama_id=chama_id, transaction_id=txn.id)
    assert "already been reversed" in str(exc.value).lower()


def test_reversal_of_reversal_rejected(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    service = LedgerService(db)
    txn = _post(db, actor, chama_id, cash.id, equity.id)
    reversal = service.reverse_transaction(actor=actor, chama_id=chama_id, transaction_id=txn.id)

    with pytest.raises(Exception) as exc:
        service.reverse_transaction(actor=actor, chama_id=chama_id, transaction_id=reversal.id)
    assert "cannot be reversed" in str(exc.value)


def test_ledger_read_requires_active_membership(client, db):
    headers_a, chama_id, cash, equity = _setup(client, db, email="a@example.com",
                                               phone="+254700000001", govt="GID-001")
    actor_a = _get_user(db, "a@example.com")
    _post(db, actor_a, chama_id, cash.id, equity.id)

    headers_b = register_and_login(client, email="stranger@example.com")
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger", headers=headers_b)
    assert r.status_code == 403


def test_ledger_read_is_chama_scoped(client, db):
    headers_a, chama_a, cash_a, equity_a = _setup(client, db, email="a@example.com",
                                                  phone="+254700000001", govt="GID-001")
    headers_b, chama_b, cash_b, equity_b = _setup(client, db, email="b@example.com",
                                                  phone="+254700000002", govt="GID-002")
    actor_a = _get_user(db, "a@example.com")
    actor_b = _get_user(db, "b@example.com")
    _post(db, actor_a, chama_a, cash_a.id, equity_a.id)
    _post(db, actor_b, chama_b, cash_b.id, equity_b.id)

    r = client.get(f"/api/v1/chamas/{chama_a}/ledger", headers=headers_a)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1


def test_ledger_unauthenticated(client, db):
    r = client.get(f"/api/v1/chamas/{uuid.uuid4()}/ledger")
    assert r.status_code == 401


def test_ledger_transaction_count_by_source(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    for i in range(3):
        LedgerService(db).post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type="TEST",
            source_id=uuid.uuid4(),
            description=f"t{i}",
            lines=[
                LedgerLine(account_id=cash.id, debit=Decimal("50.00")),
                LedgerLine(account_id=equity.id, credit=Decimal("50.00")),
            ],
        )

    txns = LedgerService(db).list_by_chama(actor=actor, chama_id=chama_id)
    assert len(txns) == 3
    assert len(db.scalars(select(LedgerTransaction)).all()) == 3