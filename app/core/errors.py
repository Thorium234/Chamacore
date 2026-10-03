"""Application errors translated to structured HTTP responses."""


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class PasswordChangeRequiredError(PermissionDeniedError):
    """Authentication succeeded, but the account must change its password."""

    code = "PASSWORD_CHANGE_REQUIRED"


class StateError(AppError):
    status_code = 400
    code = "INVALID_STATE"


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class WebhookRejectedError(AppError):
    status_code = 400
    code = "WEBHOOK_REJECTED"
