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


# --- V3 payment enums (ADR-016, ADR-017, ADR-018) ---


class PaymentProviderCode(StrEnum):
    JENGA = "JENGA"
    DARAJA = "DARAJA"


class PaymentEnvironment(StrEnum):
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


class PaymentConnectionStatus(StrEnum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    INVALID = "INVALID"


class PaymentConnectionAuditAction(StrEnum):
    CREATED = "CREATED"
    CREDENTIALS_REPLACED = "CREDENTIALS_REPLACED"
    VALIDATED = "VALIDATED"
    TESTED = "TESTED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    DELETED = "DELETED"


class PaymentIntentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class PaymentAttemptStatus(StrEnum):
    INITIATED = "INITIATED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class ProviderTransactionStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class PaymentEventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    DEDUPLICATED = "DEDUPLICATED"
    REJECTED = "REJECTED"
    UNPROCESSABLE = "UNPROCESSABLE"
    DISAGREEMENT = "DISAGREEMENT"


class PaymentCapability(StrEnum):
    STK_PUSH = "STK_PUSH"
    PAYMENT_REQUEST = "PAYMENT_REQUEST"
    PAYMENT_STATUS_QUERY = "PAYMENT_STATUS_QUERY"
    CALLBACKS = "CALLBACKS"
    REFUNDS = "REFUNDS"


class PaymentTransferSource(StrEnum):
    CLIENT = "CLIENT"
    PROVIDER_CALLBACK = "PROVIDER_CALLBACK"
    STATUS_QUERY = "STATUS_QUERY"
    SYSTEM = "SYSTEM"