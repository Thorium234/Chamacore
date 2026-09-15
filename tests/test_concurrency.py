"""Concurrency test: membership numbers are safe under concurrent creation."""

import threading

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.chama import Chama
from app.models.enums import MembershipStatus, RoleName
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_sequence import MembershipSequence
from app.models.role import Role
from app.repositories.membership import MembershipRepository
from app.services.membership import MAX_NUMBER_RETRIES

import app.models  # noqa: F401


class TestMembershipNumberConcurrency:
    def test_concurrent_numbers_are_unique(self, tmp_path):
        db_path = tmp_path / "concurrent.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", lambda c, e: c.execute("PRAGMA journal_mode=WAL"))
        Base.metadata.create_all(engine)
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        # Seed roles
        session = sf()
        for rn in RoleName:
            session.add(Role(name=rn.value))

        # Create a user (member_id=None, we won't test auth — just sequence)
        from app.models.user import User
        from app.core.security import hash_password

        user = User(email="creator@e.com", password_hash=hash_password("x"))
        session.add(user)
        session.flush()

        chama = Chama(name="C", created_by_user_id=user.id, registration_fee_amount=0)
        session.add(chama)
        session.flush()

        # creator membership = number 1
        creator = Member(first_name="Creator", last_name="X", phone_number="+254700000000", government_id="GID-0")
        session.add(creator)
        session.flush()
        m1 = Membership(chama_id=chama.id, member_id=creator.id, membership_number=1, status=MembershipStatus.ACTIVE)
        session.add(m1)
        session.flush()
        session.add(MembershipSequence(chama_id=chama.id, next_number=2))
        session.commit()
        chama_id = chama.id
        session.close()

        errors: list[tuple[int, BaseException]] = []

        def create_member(i):
            # Mirror the service's concurrency protocol: locked allocation,
            # unique-constraint backstop, bounded retry on number collisions.
            for attempt in range(MAX_NUMBER_RETRIES):
                try:
                    s = sf()
                    member = Member(
                        first_name=f"Member{i}",
                        last_name="T",
                        phone_number=f"+2547000{i:04d}",
                        government_id=f"GID-{i:04d}",
                    )
                    s.add(member)
                    s.flush()
                    number = MembershipRepository(s).allocate_membership_number(chama_id)
                    MembershipRepository(s).create(
                        chama_id=chama_id,
                        member_id=member.id,
                        membership_number=number,
                    )
                    s.commit()
                    break
                except IntegrityError as exc:
                    s.rollback()
                    if "membership_number" in str(exc.orig) and attempt < MAX_NUMBER_RETRIES - 1:
                        continue
                    raise

        threads = [threading.Thread(target=create_member, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"concurrency errors: {errors}"

        s = sf()
        numbers = sorted(
            r[0]
            for r in s.execute(
                select(Membership.membership_number).where(Membership.chama_id == chama_id)
            ).fetchall()
        )
        s.close()
        assert len(numbers) == 21  # creator (1) + 20 new members
        assert numbers == list(range(1, 22))