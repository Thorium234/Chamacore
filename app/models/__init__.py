"""Import all models so that Base.metadata is complete."""

from app.models.chama import Chama
from app.models.contribution import Contribution
from app.models.enums import (
    ChamaStatus,
    ContributionStatus,
    MembershipStatus,
    RegistrationFeeStatus,
    RoleName,
    ShareStatus,
)
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_role import MembershipRole
from app.models.membership_sequence import MembershipSequence
from app.models.registration_fee import RegistrationFee
from app.models.role import Role
from app.models.share import Share
from app.models.user import User

__all__ = [
    "Chama",
    "ChamaStatus",
    "Contribution",
    "ContributionStatus",
    "Member",
    "Membership",
    "MembershipRole",
    "MembershipSequence",
    "MembershipStatus",
    "RegistrationFee",
    "RegistrationFeeStatus",
    "Role",
    "RoleName",
    "Share",
    "ShareStatus",
    "User",
]