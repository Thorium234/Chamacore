"""Password policy enforcement (server-side)."""

import re
from collections.abc import Sequence

from app.core.errors import AppError

COMMON_PASSWORDS = {
    "password",
    "password123",
    "Password123",
    "qwerty123",
    "admin123",
    "letmein123",
    "welcome123",
    "changeme123",
    "1234567890",
    "12345678",
    "password1",
    "abc123456",
    "secret123",
}


class PasswordPolicyViolationError(AppError):
    status_code = 400
    code = "PASSWORD_POLICY_VIOLATION"

    def __init__(self, violations: Sequence[str]):
        self.violations = list(violations)
        message = "; ".join(self.violations) if self.violations else "Password does not meet policy"
        super().__init__(message)


def _has_digit(s: str) -> bool:
    return any(c.isdigit() for c in s)


def _has_upper(s: str) -> bool:
    return any(c.isupper() for c in s)


def _has_lower(s: str) -> bool:
    return any(c.islower() for c in s)


def _has_symbol(s: str) -> bool:
    return bool(re.search(r"[^A-Za-z0-9]", s))


def validate_password(password: str, *, email: str | None = None, phone: str | None = None) -> None:
    """Validate password meets minimum complexity requirements.

    Rules (aligned with gap report):
    - Minimum length 10
    - At least one upper, one lower, one digit, one symbol
    - Not a common password
    - Must not equal email or phone (case-insensitive)
    """
    violations: list[str] = []
    if len(password) < 10:
        violations.append("Password must be at least 10 characters long")

    if not (_has_upper(password) and _has_lower(password) and _has_digit(password) and _has_symbol(password)):
        violations.append("Password must include at least one uppercase letter, one lowercase letter, one digit, and one symbol")

    pw_lower = password.lower()
    if pw_lower in COMMON_PASSWORDS:
        violations.append("Password is too common")

    if email and pw_lower == email.lower():
        violations.append("Password must not be the same as your email")
    if phone:
        phone_clean = re.sub(r"\D", "", phone)
        pw_clean = re.sub(r"\D", "", pw_lower)
        if pw_clean and phone_clean and (pw_clean in phone_clean or phone_clean in pw_clean or pw_lower == phone.lower()):
            violations.append("Password must not be the same as your phone number")

    if violations:
        raise PasswordPolicyViolationError(violations)
