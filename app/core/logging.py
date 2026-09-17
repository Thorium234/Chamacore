"""Structured JSON logging with a per-request correlation ID.

Every emitted record carries a ``request_id`` read from a request-scoped
``ContextVar``. Clients may supply their own id via the ``X-Request-ID``
header; the middleware echoes it back on the response. The root handler is
added idempotently so configuring logging does not replace an existing test
harness or framework handler.
"""

import json
import logging
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"
_FALLBACK_REQUEST_ID = "-"
_EXTRA_FIELDS = ("code", "method", "path", "status", "duration_ms", "client")

_request_id: ContextVar[str] = ContextVar(
    "chamacore_request_id", default=_FALLBACK_REQUEST_ID
)


def get_request_id() -> str:
    """Return the active request correlation id (``-`` outside a request)."""
    return _request_id.get()


def set_request_id(request_id: str):
    """Set the correlation id for the current request and return its token."""
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    """Restore the previous correlation id after a request completes."""
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for machine consumption."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", _FALLBACK_REQUEST_ID),
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if field != "message":
                    payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, debug: bool) -> None:
    """Install the JSON handler once; keep any existing handlers intact."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    if any(isinstance(getattr(handler, "formatter", None), JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)