"""Pagination (limit/offset) coverage for list repositories that gained it (docs/14 P2#1).

Repository-level tests seed rows directly (no HTTP/auth cost) and assert that
``limit``/``offset`` slice the same stable order as the unfiltered full list.
API-level tests prove the query parameters are plumbed through and validated.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from tests.conftest import add_membership, create_chama, register_and_login

from app.models import (
    AuditEvent,
    Chama,
    Contribution,
    Loan,
    LoanRepayment,
    Member,
    Membership,
    PaymentConnection,
    PaymentIntent,
    Payout,
    User,
)
from app.models.enums import (
    MembershipStatus,
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentProviderCode,
    PaymentIntentStatus,
)
from app.repositories.audit import AuditRepository
from app.repositories.contribution import ContributionRepository
from app.repositories.loan import LoanRepository
from app.repositories.loan_repayment import LoanRepaymentRepository
from app.repositories.membership import MembershipRepository
from app.repositories.payment import PaymentConnectionRepository, PaymentIntentRepository
from app.repositories.payout import PayoutRepository

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _user(db, email: str = "seed@test.local"):
    u = User(email=email, password_hash="x")
    db.add(u)
    db.flush()
    return u


def _member(db, phone: str, govt: str):
    m = Member(first_name="Seed", last_name="Row", phone_number=phone, government_id=govt)
    db.add(m)
    db.flush()
    return m


def _chama(db, user: User):
    c = Chama(name=f"Seed Chama {uuid.uuid4().hex[:8]}", registration_fee_amount=Decimal("100.00"), created_by_user_id=user.id)
    db.add(c)
    db.flush()
    return c


def _membership(db, chama: Chama, member: Member, number: int):
    m = Membership(
        chama_id=chama.id,
        member_id=member.id,
        membership_number=number,
        status=MembershipStatus.ACTIVE,
    )
    db.add(m)
    db.flush()
    return m


def _seed(db):
    """Return a seeded (user, chama) pair with one ACTIVE membership."""
    user = _user(db)
    chama = _chama(db, user)
    member = _member(db, "+254000000001", "GID-SEED-1")
    _membership(db, chama, member, 1)
    db.commit()
    return user, chama


def _memberships(db, chama: Chama):
    return list(
        db.scalars(select(Membership).where(Membership.chama_id == chama.id).order_by(Membership.membership_number))
    )


def _seed_memberships(db, user: User, chama: Chama, count: int):
    """Append ``count`` extra ACTIVE memberships (unique phone/government id)."""
    base = len(_memberships(db, chama))
    for i in range(base, base + count):
        db.add(
            _membership(
                db,
                chama,
                _member(db, f"+2540000{i+10:06d}", f"GID-SEED-X{i}"),
                i + 1,
            )
        )


class TestContributionPagination:
    def test_limit_and_offset_slice_stable_order(self, db):
        user, chama = _seed(db)
        _seed_memberships(db, user, chama, 4)
        db.flush()
        for i, membership in enumerate(_memberships(db, chama)):
            db.add(
                Contribution(
                    membership_id=membership.id,
                    amount=Decimal("100.00"),
                    period=f"2026-{i + 1:02d}",
                    recorded_by_user_id=user.id,
                    created_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = ContributionRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 5
        page = repo.list_by_chama(chama.id, limit=2, offset=2)
        assert [c.id for c in page] == [c.id for c in full[2:4]]
        assert repo.list_by_chama(chama.id, limit=10, offset=3) == full[3:]

    def test_id_tiebreaker_keeps_pagination_offsets_stable(self, db):
        user, chama = _seed(db)
        _seed_memberships(db, user, chama, 5)
        db.flush()
        for membership in _memberships(db, chama):
            db.add(
                Contribution(
                    membership_id=membership.id,
                    amount=Decimal("100.00"),
                    period="2026-09",
                    recorded_by_user_id=user.id,
                    created_at=T0,
                )
            )
        db.commit()

        repo = ContributionRepository(db)
        first = repo.list_by_chama(chama.id)
        second = repo.list_by_chama(chama.id)
        assert len(first) == 6
        assert [c.id for c in first] == [c.id for c in second]
        assert len(repo.list_by_chama(chama.id, limit=None, offset=0)) == 6


class TestMembershipPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        for i in range(1, 5):
            _membership(
                db,
                chama,
                _member(db, f"+2540000000{i+1:02d}", f"GID-SEED-{i+1}"),
                i + 1,
            )
        db.commit()

        repo = MembershipRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 5
        assert [m.id for m in repo.list_by_chama(chama.id, limit=2, offset=2)] == [
            m.id for m in full[2:4]
        ]


class TestLoanPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        membership = chama.memberships[0]
        for i in range(4):
            db.add(
                Loan(
                    chama_id=chama.id,
                    membership_id=membership.id,
                    principal=Decimal("1000.00"),
                    interest_rate=Decimal("0.10"),
                    term_months=12,
                    application_date=T0.date() + timedelta(days=i),
                    recorded_by_user_id=user.id,
                    created_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = LoanRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 4
        assert [l.id for l in repo.list_by_chama(chama.id, limit=1, offset=1)] == [
            l.id for l in full[1:2]
        ]
        assert [l.id for l in repo.list_by_membership(membership.id, limit=2, offset=0)] == [
            l.id for l in full[:2]
        ]


class TestLoanRepaymentPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        membership = chama.memberships[0]
        loan = Loan(
            chama_id=chama.id,
            membership_id=membership.id,
            principal=Decimal("1000.00"),
            interest_rate=Decimal("0.10"),
            term_months=12,
            application_date=T0.date(),
            recorded_by_user_id=user.id,
        )
        db.add(loan)
        db.flush()
        for i in range(4):
            db.add(
                LoanRepayment(
                    chama_id=chama.id,
                    loan_id=loan.id,
                    amount=Decimal("250.00"),
                    principal_portion=Decimal("200.00"),
                    interest_portion=Decimal("50.00"),
                    recorded_by_user_id=user.id,
                    recorded_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = LoanRepaymentRepository(db)
        full = repo.list_by_loan(loan.id)
        assert len(full) == 4
        assert [r.id for r in repo.list_by_loan(loan.id, limit=3, offset=1)] == [
            r.id for r in full[1:4]
        ]


class TestPayoutPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        membership = chama.memberships[0]
        for i in range(4):
            db.add(
                Payout(
                    chama_id=chama.id,
                    membership_id=membership.id,
                    amount=Decimal("100.00"),
                    requested_by_user_id=user.id,
                    requested_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = PayoutRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 4
        assert [p.id for p in repo.list_by_chama(chama.id, limit=2, offset=2)] == [
            p.id for p in full[2:4]
        ]


class TestAuditPagination:
    def test_default_limit_and_offset(self, db):
        user, chama = _seed(db)
        for i in range(205):
            db.add(
                AuditEvent(
                    chama_id=chama.id,
                    actor_user_id=user.id,
                    action="seed.action",
                    resource_type="chama",
                    resource_id=chama.id,
                    success=True,
                    created_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = AuditRepository(db)
        assert len(repo.list_by_chama(chama.id)) == 200
        assert len(repo.list_by_chama(chama.id, offset=200)) == 5
        assert len(repo.list_by_chama(chama.id, limit=500)) == 205
        assert len(repo.list_by_chama(chama.id, limit=10, offset=200)) == 5


class TestPaymentConnectionPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        combos = [
            (PaymentProviderCode.DARAJA, PaymentEnvironment.SANDBOX),
            (PaymentProviderCode.DARAJA, PaymentEnvironment.PRODUCTION),
            (PaymentProviderCode.JENGA, PaymentEnvironment.SANDBOX),
        ]
        for i, (provider, env) in enumerate(combos):
            db.add(
                PaymentConnection(
                    chama_id=chama.id,
                    provider_code=provider,
                    environment=env,
                    status=PaymentConnectionStatus.ACTIVE,
                    encrypted_credentials="sealed",
                    masked_account_identifier="6000",
                    created_by_user_id=user.id,
                    updated_by_user_id=user.id,
                )
            )
        db.commit()

        repo = PaymentConnectionRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 3
        assert [c.id for c in repo.list_by_chama(chama.id, limit=1, offset=1)] == [
            c.id for c in full[1:2]
        ]


class TestPaymentIntentPagination:
    def test_limit_and_offset(self, db):
        user, chama = _seed(db)
        membership = chama.memberships[0]
        for i in range(4):
            db.add(
                PaymentIntent(
                    chama_id=chama.id,
                    membership_id=membership.id,
                    amount=Decimal("100.00"),
                    purpose="contribution",
                    status=PaymentIntentStatus.PENDING,
                    idempotency_key=f"seed-{i}",
                    idempotency_payload_hash="x",
                    created_by_user_id=user.id,
                    created_at=T0 + timedelta(minutes=i),
                )
            )
        db.commit()

        repo = PaymentIntentRepository(db)
        full = repo.list_by_chama(chama.id)
        assert len(full) == 4
        assert [i2.id for i2 in repo.list_by_chama(chama.id, limit=2, offset=2)] == [
            i2.id for i2 in full[2:4]
        ]


class TestListEndpointsApi:
    def test_memberships_limit_offset_and_validation(self, client):
        headers = register_and_login(client, "page@e.com")
        chama = create_chama(client, headers, fee="0.00")
        add_membership(client, headers, chama["id"], phone="+254700010101", govt="GID-P1")
        add_membership(client, headers, chama["id"], phone="+254700010102", govt="GID-P2")
        add_membership(client, headers, chama["id"], phone="+254700010103", govt="GID-P3")

        url = f"/api/v1/chamas/{chama['id']}/memberships"
        full = client.get(url, headers=headers)
        assert full.status_code == 200
        assert len(full.json()) == 4
        page = client.get(url, headers=headers, params={"limit": 2, "offset": 2})
        assert page.status_code == 200
        assert len(page.json()) == 2
        assert [m["id"] for m in page.json()] == [m["id"] for m in full.json()[2:4]]

        for bad in (
            {"limit": 0},
            {"limit": 501},
            {"offset": -1},
            {"limit": "x"},
        ):
            assert client.get(url, headers=headers, params=bad).status_code == 422

    def test_audit_events_limit_and_default(self, client):
        headers = register_and_login(client, "auditpage@e.com")
        chama = create_chama(client, headers, fee="0.00")
        add_membership(client, headers, chama["id"], phone="+254700020201", govt="GID-A1")

        url = f"/api/v1/chamas/{chama['id']}/audit-events"
        all_events = client.get(url, headers=headers).json()
        assert client.get(url, headers=headers, params={"limit": 2, "offset": 0}).status_code == 200
        limited = client.get(url, headers=headers, params={"limit": 2, "offset": 0}).json()
        assert len(limited) == 2
        assert [e["id"] for e in limited] == [e["id"] for e in all_events[:2]]
        assert client.get(url, headers=headers, params={"limit": 501}).status_code == 422
