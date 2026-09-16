"""V2 ledger database-guard tests.

These verify that the database itself (not just the service layer) rejects
immutable-ledger writes, cross-Chama ledger relationships, unsupported
account types, and duplicate reversals. They exercise the schema constraints
and the guard triggers installed by the migration and the test harness.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.enums import LedgerAccountType
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_transaction import LedgerTransaction
from app.services.ledger import REVERSAL_SOURCE_TYPE

from tests.test_ledger import _add_account, _get_user, _post, _setup


def _first_entry(db, transaction_id: uuid.UUID) -> LedgerEntry:
    return db.scalars(
        select(LedgerEntry).where(LedgerEntry.transaction_id == transaction_id)
    ).first()


def test_db_blocks_update_of_ledger_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    with pytest.raises(DBAPIError):
        stored = db.get(LedgerTransaction, txn.id)
        stored.description = "tampered"
        db.commit()
    db.rollback()

    fresh = db.get(LedgerTransaction, txn.id)
    assert fresh.description == "test posting"


def test_db_blocks_delete_of_ledger_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    with pytest.raises(DBAPIError):
        db.delete(db.get(LedgerTransaction, txn.id))
        db.commit()
    db.rollback()

    assert db.get(LedgerTransaction, txn.id) is not None
    assert len(db.scalars(select(LedgerTransaction)).all()) == 1


def test_db_blocks_update_of_ledger_entry(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    with pytest.raises(DBAPIError):
        entry = _first_entry(db, txn.id)
        entry.credit = Decimal("10.00")
        db.commit()
    db.rollback()

    entry = _first_entry(db, txn.id)
    assert entry.credit == Decimal("0.00")


def test_db_blocks_delete_of_ledger_entry(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    with pytest.raises(DBAPIError):
        db.delete(_first_entry(db, txn.id))
        db.commit()
    db.rollback()

    assert len(db.scalars(select(LedgerEntry)).all()) == 2


def test_db_rejects_cross_chama_ledger_entry(client, db):
    _, chama_a, cash_a, equity_a = _setup(client, db, email="a@example.com",
                                          phone="+254700000001", govt="GID-001")
    _, chama_b, cash_b, _ = _setup(client, db, email="b@example.com",
                                   phone="+254700000002", govt="GID-002")
    actor_a = _get_user(db, "a@example.com")
    txn_a = _post(db, actor_a, chama_a, cash_a.id, equity_a.id)
    entries_before = len(db.scalars(select(LedgerEntry)).all())

    with pytest.raises(DBAPIError):
        db.add(
            LedgerEntry(
                chama_id=chama_a,
                transaction_id=txn_a.id,
                account_id=cash_b.id,
                debit=Decimal("1.00"),
                credit=Decimal("0.00"),
            )
        )
        db.commit()
    db.rollback()

    assert len(db.scalars(select(LedgerEntry)).all()) == entries_before


def test_db_rejects_cross_chama_reversal(client, db):
    _, chama_a, cash_a, equity_a = _setup(client, db, email="a@example.com",
                                          phone="+254700000001", govt="GID-001")
    _, chama_b, cash_b, equity_b = _setup(client, db, email="b@example.com",
                                          phone="+254700000002", govt="GID-002")
    actor_a = _get_user(db, "a@example.com")
    actor_b = _get_user(db, "b@example.com")
    txn_a = _post(db, actor_a, chama_a, cash_a.id, equity_a.id)
    txn_b = _post(db, actor_b, chama_b, cash_b.id, equity_b.id)
    transactions_before = len(db.scalars(select(LedgerTransaction)).all())

    with pytest.raises(DBAPIError):
        db.add(
            LedgerTransaction(
                chama_id=chama_a,
                source_type=REVERSAL_SOURCE_TYPE,
                source_id=uuid.uuid4(),
                description="cross-chama reversal",
                posted_by_user_id=actor_a.id,
                reverses_transaction_id=txn_b.id,
            )
        )
        db.commit()
    db.rollback()

    assert len(db.scalars(select(LedgerTransaction)).all()) == transactions_before
    assert txn_a.id is not None


def test_db_rejects_unsupported_account_type(client, db):
    _, chama_id, _, _ = _setup(client, db)

    with pytest.raises(DBAPIError):
        db.add(
            LedgerAccount(
                chama_id=chama_id,
                code="9999",
                name="Bogus",
                account_type="BOGUS",
            )
        )
        db.commit()
    db.rollback()

    assert db.scalars(
        select(LedgerAccount).where(LedgerAccount.code == "9999")
    ).first() is None


def test_db_rejects_blank_account_code(client, db):
    _, chama_id, _, _ = _setup(client, db)

    with pytest.raises(DBAPIError):
        db.add(
            LedgerAccount(
                chama_id=chama_id,
                code="   ",
                name="No Code",
                account_type=LedgerAccountType.ASSET,
            )
        )
        db.commit()
    db.rollback()


def test_db_rejects_blank_account_name(client, db):
    _, chama_id, _, _ = _setup(client, db)

    with pytest.raises(DBAPIError):
        db.add(
            LedgerAccount(
                chama_id=chama_id,
                code="9998",
                name="  ",
                account_type=LedgerAccountType.ASSET,
            )
        )
        db.commit()
    db.rollback()


def test_db_blocks_second_reversal_of_same_transaction(client, db):
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    def _insert_reversal(source_id: uuid.UUID) -> None:
        reversal = LedgerTransaction(
            chama_id=chama_id,
            source_type=REVERSAL_SOURCE_TYPE,
            source_id=source_id,
            description="reversal",
            posted_by_user_id=actor.id,
            reverses_transaction_id=txn.id,
        )
        db.add(reversal)
        db.flush()
        db.add_all(
            [
                LedgerEntry(
                    chama_id=chama_id,
                    transaction_id=reversal.id,
                    account_id=cash.id,
                    debit=Decimal("0.00"),
                    credit=Decimal("100.00"),
                ),
                LedgerEntry(
                    chama_id=chama_id,
                    transaction_id=reversal.id,
                    account_id=equity.id,
                    debit=Decimal("100.00"),
                    credit=Decimal("0.00"),
                ),
            ]
        )
        db.commit()

    _insert_reversal(uuid.uuid4())

    with pytest.raises(DBAPIError):
        _insert_reversal(uuid.uuid4())
    db.rollback()

    reversals = db.scalars(
        select(LedgerTransaction).where(
            LedgerTransaction.reverses_transaction_id == txn.id
        )
    ).all()
    assert len(reversals) == 1


def test_service_populates_chama_id_on_entries(client, db):
    """The denormalized chama_id on entries is written by the posting path."""
    headers, chama_id, cash, equity = _setup(client, db)
    actor = _get_user(db, "user@example.com")
    txn = _post(db, actor, chama_id, cash.id, equity.id)

    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.transaction_id == txn.id)
    ).all()
    assert len(entries) == 2
    assert all(entry.chama_id == chama_id for entry in entries)