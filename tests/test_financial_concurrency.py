"""Cash-serialization race tests for financial admission (P1#3).

Loan disbursement and payout completion both read ``available_chama_cash`` and
then reduce Cash. Under concurrent execution two approved decisions could each
observe the full balance and collectively overspend the Chama.

The services serialize these decisions with ``SELECT ... FOR UPDATE`` on the
Chama's Cash ledger account row (``lock_cash_account``). These tests prove the
guarantee: race two cash reductions whose sum exceeds the balance and require
exactly one winner and a never-negative Cash balance.

The row lock is a PostgreSQL mechanism; on SQLite the clause is a no-op, so
these tests only run when ``CHAMACORE_DATABASE_URL`` points at PostgreSQL.
"""

import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import StateError
from app.core.security import hash_password
from app.db.audit_guards import create_audit_guards
from app.db.base import Base
from app.db.ledger_guards import create_ledger_guards
from app.models.chama import Chama
from app.models.enums import LoanStatus, MembershipStatus, PayoutStatus, RoleName
from app.models.ledger_account import LedgerAccount
from app.models.loan import Loan
from app.models.ledger_transaction import LedgerTransaction
from app.models.member import Member
from app.models.membership import Membership
from app.models.payout import Payout
from app.models.role import Role
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.services.finance import available_chama_cash
from app.services.ledger import (
    CASH_CODE,
    CONTRIBUTION_SOURCE_TYPE,
    LOAN_DISBURSEMENT_SOURCE_TYPE,
    LOANS_RECEIVABLE_CODE,
    PAYOUT_COMPLETION_SOURCE_TYPE,
    SHARE_CAPITAL_CODE,
    LedgerLine,
    LedgerService,
)
from app.services.loan import LoanService
from app.services.payout import PayoutService

import app.models  # noqa: F401

from tests.conftest import TEST_DATABASE_URL

pytestmark = [
    pytest.mark.concurrency,
    pytest.mark.skipif(
        not (TEST_DATABASE_URL or "").startswith("postgresql"),
        reason="cash-lock serialization is proven on PostgreSQL (set CHAMACORE_DATABASE_URL)",
    ),
]


def _seed_scenario(engine):
    """Build a funded Chama with two PROCESSING payouts and two APPROVED loans.

    Cash is seeded at 500.00; each pair's amounts (400 and 300) cannot both be
    admitted. Returns the reusable ids, the detached actor, and the sessionmaker.
    """
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    seed = sf()
    existing = set(seed.execute(select(Role.name)).scalars().all())
    roles = {}
    for rn in RoleName:
        if rn.value not in existing:
            role = Role(name=rn.value)
            seed.add(role)
            seed.flush()
            roles[rn] = role
        else:
            roles[rn] = seed.scalar(select(Role).where(Role.name == rn.value))

    user = User(email="finance@e.com", password_hash=hash_password("x"))
    seed.add(user)
    seed.flush()
    chama = Chama(name="Finance Concurrency", created_by_user_id=user.id, registration_fee_amount=0)
    seed.add(chama)
    seed.flush()
    member = Member(
        first_name="Finance", last_name="Test", phone_number="+254700002222", government_id="GID-FIN-1"
    )
    seed.add(member)
    seed.flush()
    user.member_id = member.id
    membership = Membership(
        chama_id=chama.id, member_id=member.id, membership_number=1, status=MembershipStatus.ACTIVE
    )
    seed.add(membership)
    seed.flush()
    MembershipRepository(seed).add_role(membership.id, roles[RoleName.CHAIRPERSON])
    MembershipRepository(seed).add_role(membership.id, roles[RoleName.TREASURER])

    LedgerService(seed).seed_default_chart_of_accounts(chama.id)
    cash_id = seed.scalar(
        select(LedgerAccount.id).where(
            LedgerAccount.chama_id == chama.id, LedgerAccount.code == CASH_CODE
        )
    )
    equity_id = seed.scalar(
        select(LedgerAccount.id).where(
            LedgerAccount.chama_id == chama.id, LedgerAccount.code == SHARE_CAPITAL_CODE
        )
    )
    receivable_id = seed.scalar(
        select(LedgerAccount.id).where(
            LedgerAccount.chama_id == chama.id, LedgerAccount.code == LOANS_RECEIVABLE_CODE
        )
    )
    if receivable_id is None:
        raise RuntimeError("loans receivable account was not seeded")
    LedgerService(seed).post_transaction(
        actor=user,
        chama_id=chama.id,
        source_type=CONTRIBUTION_SOURCE_TYPE,
        source_id=uuid.uuid4(),
        description="seed chama cash",
        lines=[
            LedgerLine(account_id=cash_id, debit=Decimal("500.00")),
            LedgerLine(account_id=equity_id, credit=Decimal("500.00")),
        ],
    )

    payouts = [
        Payout(
            chama_id=chama.id,
            membership_id=membership.id,
            amount=Decimal("400.00"),
            status=PayoutStatus.PROCESSING,
            requested_by_user_id=user.id,
        ),
        Payout(
            chama_id=chama.id,
            membership_id=membership.id,
            amount=Decimal("300.00"),
            status=PayoutStatus.PROCESSING,
            requested_by_user_id=user.id,
        ),
    ]
    loans = [
        Loan(
            chama_id=chama.id,
            membership_id=membership.id,
            principal=Decimal("400.00"),
            interest_rate=Decimal("0.05"),
            term_months=3,
            status=LoanStatus.APPROVED,
            recorded_by_user_id=user.id,
            approval_date=datetime.utcnow(),
            approved_by_user_id=user.id,
        ),
        Loan(
            chama_id=chama.id,
            membership_id=membership.id,
            principal=Decimal("300.00"),
            interest_rate=Decimal("0.05"),
            term_months=3,
            status=LoanStatus.APPROVED,
            recorded_by_user_id=user.id,
            approval_date=datetime.utcnow(),
            approved_by_user_id=user.id,
        ),
    ]
    seed.add_all(payouts + loans)
    seed.commit()
    chama_id = chama.id
    seed.close()
    return {
        "sf": sf,
        "chama_id": chama_id,
        "user": user,
        "payout_ids": [p.id for p in payouts],
        "loan_ids": [l.id for l in loans],
    }


def _worker_complete(payout_id, chama_id, user, sf, results, lock):
    session = sf()
    try:
        PayoutService(session).complete(actor=user, chama_id=chama_id, payout_id=payout_id)
        outcome = "ok"
    except StateError as exc:
        outcome = f"state:{exc}"
    except Exception as exc:  # noqa: BLE001
        outcome = f"error:{exc!r}"
    finally:
        session.close()
    with lock:
        results.append(outcome)


def _worker_disburse(loan_id, chama_id, user, sf, results, lock):
    session = sf()
    try:
        LoanService(session).disburse(actor=user, chama_id=chama_id, loan_id=loan_id)
        outcome = "ok"
    except StateError as exc:
        outcome = f"state:{exc}"
    except Exception as exc:  # noqa: BLE001
        outcome = f"error:{exc!r}"
    finally:
        session.close()
    with lock:
        results.append(outcome)


class TestPayoutCompletionSerialization:
    def test_concurrent_completions_never_overspend_cash(self, tmp_path):
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            create_ledger_guards(conn)
            create_audit_guards(conn)
        scenario = _seed_scenario(engine)
        try:
            results = []
            lock = threading.Lock()
            threads = [
                threading.Thread(
                    target=_worker_complete,
                    args=(scenario["payout_ids"][i],),
                    kwargs={
                        "chama_id": scenario["chama_id"],
                        "user": scenario["user"],
                        "sf": scenario["sf"],
                        "results": results,
                        "lock": lock,
                    },
                )
                for i in range(2)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)

            errors = [r for r in results if r.startswith("error:")]
            assert errors == []
            assert results.count("ok") == 1
            insufficient = [r for r in results if r.startswith("state:") and "Insufficient" in r]
            assert len(insufficient) == 1, f"expected one insufficient-cash rejection, got {results}"

            session = scenario["sf"]()
            cash = available_chama_cash(session, scenario["chama_id"])
            completed = list(
                session.scalars(
                    select(Payout).where(
                        Payout.chama_id == scenario["chama_id"],
                        Payout.status == PayoutStatus.COMPLETED,
                    )
                )
            )
            postings = list(
                session.scalars(
                    select(LedgerTransaction).where(
                        LedgerTransaction.source_type == PAYOUT_COMPLETION_SOURCE_TYPE
                    )
                )
            )
            session.close()
            assert cash > 0 and cash in (Decimal("100.00"), Decimal("200.00")), cash
            assert len(completed) == 1
            assert len(postings) == 1
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()


class TestLoanDisbursementSerialization:
    def test_concurrent_disbursements_never_overspend_cash(self, tmp_path):
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            create_ledger_guards(conn)
            create_audit_guards(conn)
        scenario = _seed_scenario(engine)
        try:
            results = []
            lock = threading.Lock()
            threads = [
                threading.Thread(
                    target=_worker_disburse,
                    args=(scenario["loan_ids"][i],),
                    kwargs={
                        "chama_id": scenario["chama_id"],
                        "user": scenario["user"],
                        "sf": scenario["sf"],
                        "results": results,
                        "lock": lock,
                    },
                )
                for i in range(2)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)

            errors = [r for r in results if r.startswith("error:")]
            assert errors == []
            assert results.count("ok") == 1
            insufficient = [r for r in results if r.startswith("state:") and "Insufficient" in r]
            assert len(insufficient) == 1, f"expected one insufficient-cash rejection, got {results}"

            session = scenario["sf"]()
            cash = available_chama_cash(session, scenario["chama_id"])
            disbursed = list(
                session.scalars(
                    select(Loan).where(
                        Loan.chama_id == scenario["chama_id"],
                        Loan.status == LoanStatus.DISBURSED,
                    )
                )
            )
            postings = list(
                session.scalars(
                    select(LedgerTransaction).where(
                        LedgerTransaction.source_type == LOAN_DISBURSEMENT_SOURCE_TYPE
                    )
                )
            )
            session.close()
            assert cash > 0 and cash in (Decimal("100.00"), Decimal("200.00")), cash
            assert len(disbursed) == 1
            assert len(postings) == 1
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()