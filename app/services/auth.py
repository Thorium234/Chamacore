"""Authentication service."""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.member import MemberRepository
from app.repositories.user import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.members = MemberRepository(db)

    def register(self, *, email: str, password: str) -> User:
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")
        user = self.users.create(email=email, password_hash=hash_password(password))
        self.db.commit()
        return user

    def authenticate(self, *, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def link_member(self, *, user: User, phone_number: str, government_id: str) -> User:
        """Link the authenticated user to their member identity (approved decision)."""
        if user.member_id is not None:
            raise ConflictError("This account is already linked to a member")
        member = self.members.find_by_identity(phone_number, government_id)
        if member is None:
            raise NotFoundError("No member matches these identity details")
        existing = self.users.get_by_member_id(member.id)
        if existing is not None:
            raise ConflictError("This member identity is already linked to another account")
        user.member_id = member.id
        self.db.commit()
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))