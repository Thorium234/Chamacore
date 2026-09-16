"""Controlled enum values used across V1 models."""

from enum import StrEnum


class ChamaStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RegistrationFeeStatus(StrEnum):
    OWED = "OWED"
    WAIVED = "WAIVED"


class ContributionStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REVERSED = "REVERSED"


class ShareStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVERSED = "REVERSED"


class RoleName(StrEnum):
    CHAIRPERSON = "CHAIRPERSON"
    TREASURER = "TREASURER"
    SECRETARY = "SECRETARY"
    MEMBER = "MEMBER"


class LedgerAccountType(StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"