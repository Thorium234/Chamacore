"""Tests for V1 hardening: identity uniqueness, constraint backstops, config, health."""

import os

import pytest

from app.db.base import Base
from app.models.enums import (
    MembershipStatus,
    RegistrationFeeStatus,
    ShareStatus,
)
from app.models.member import Member
from app.models.membership import Membership
from app.models.registration_fee import RegistrationFee
from app.models.share import Share

from tests.conftest import add_membership, create_chama, register_and_login

import app.models  # noqa: F401


class TestP0IdentityClaim:
    """A Member identity may be claimed by only one User account (P0 fix)."""

    def test_second_claim_returns_409(self, client):
        chair = register_and_login(client, "chair@example.com")
        chama = create_chama(client, chair)
        add_membership(client, chair, chama["id"], phone="+254700000900", govt="GID-900")
        # First account claims the member
        first = register_and_login(client, "first@example.com")
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=first,
            json={"phone_number": "+254700000900", "government_id": "GID-900"},
        )
        assert r.status_code == 200
        # Second account tries to claim the same member
        second = register_and_login(client, "second@example.com")
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=second,
            json={"phone_number": "+254700000900", "government_id": "GID-900"},
        )
        assert r.status_code == 409

    def test_link_rejects_already_linked_account(self, client):
        headers = register_and_login(client, "creator@example.com")
        create_chama(client, headers)  # auto-links
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=headers,
            json={"phone_number": "+254700000001", "government_id": "GID-001"},
        )
        assert r.status_code == 409


class TestP1RegistrationFeeUnique:
    """Duplicate registration fee rows for one membership must be impossible."""

    def test_duplicate_fee_raises_integrity_error(self, db):
        """Direct DB-level attempt to insert two fees for one membership."""
        from app.models.chama import Chama
        from app.models.user import User
        from app.core.security import hash_password

        user = User(email="u@e.com", password_hash=hash_password("x"))
        db.add(user)
        db.flush()
        chama = Chama(name="C", created_by_user_id=user.id, registration_fee_amount=0)
        db.add(chama)
        db.flush()
        member = Member(first_name="A", last_name="B", phone_number="+254700000910", government_id="GID-910")
        db.add(member)
        db.flush()
        membership = Membership(chama_id=chama.id, member_id=member.id, membership_number=1, status=MembershipStatus.ACTIVE)
        db.add(membership)
        db.flush()
        fee1 = RegistrationFee(membership_id=membership.id, amount=0, status=RegistrationFeeStatus.OWED)
        db.add(fee1)
        db.flush()
        from sqlalchemy.exc import IntegrityError

        fee2 = RegistrationFee(membership_id=membership.id, amount=0, status=RegistrationFeeStatus.OWED)
        db.add(fee2)
        with pytest.raises(IntegrityError):
            db.flush()


class TestP1ShareUnique:
    """Duplicate share rows for one contribution must be impossible."""

    def test_duplicate_share_raises_integrity_error(self, db):
        from app.models.chama import Chama
        from app.models.contribution import Contribution
        from app.models.enums import ContributionStatus, RoleName
        from app.models.user import User
        from app.core.security import hash_password

        user = User(email="u2@e.com", password_hash=hash_password("x"))
        db.add(user)
        db.flush()
        chama = Chama(name="C2", created_by_user_id=user.id, registration_fee_amount=0)
        db.add(chama)
        db.flush()
        member = Member(first_name="C", last_name="D", phone_number="+254700000920", government_id="GID-920")
        db.add(member)
        db.flush()
        membership = Membership(chama_id=chama.id, member_id=member.id, membership_number=1, status=MembershipStatus.ACTIVE)
        db.add(membership)
        db.flush()
        contribution = Contribution(
            membership_id=membership.id,
            amount=1000,
            period="2026-09",
            status=ContributionStatus.CONFIRMED,
            recorded_by_user_id=user.id,
        )
        db.add(contribution)
        db.flush()
        share1 = Share(membership_id=membership.id, contribution_id=contribution.id, units=10, status=ShareStatus.ACTIVE)
        db.add(share1)
        db.flush()
        from sqlalchemy.exc import IntegrityError

        share2 = Share(membership_id=membership.id, contribution_id=contribution.id, units=10, status=ShareStatus.ACTIVE)
        db.add(share2)
        with pytest.raises(IntegrityError):
            db.flush()


class TestP1JWTConfig:
    """Default JWT secret must be rejected when debug is False."""

    def test_default_secret_rejected_in_production(self):
        import importlib
        from app.core import config as config_mod

        original = os.environ.pop("CHAMACORE_DEBUG", None)
        try:
            os.environ["CHAMACORE_DEBUG"] = "false"
            config_mod.get_settings.cache_clear()
            with pytest.raises(ValueError, match="CHAMACORE_JWT_SECRET_KEY"):
                config_mod.Settings()
        finally:
            if original is not None:
                os.environ["CHAMACORE_DEBUG"] = original
            else:
                os.environ.pop("CHAMACORE_DEBUG", None)
            config_mod.get_settings.cache_clear()


class TestP2HealthEndpoints:
    """Health and readiness endpoints respond correctly."""

    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_ready_returns_ready(self, client):
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json() == {"status": "ready"}
