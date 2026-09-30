"""List provider callbacks stuck in the webhook inbox (read-only recovery tool).

Every provider callback is stored as a ``PaymentEvent`` before its settlement
is applied (ADR-018). If the process crashes between storage and callback
application the event stays ``RECEIVED``; provider redelivery resumes it, so
the inbox needs an operator eyeball for events that are old enough to be stuck.

Read only: this script never marks, re-drives, or deletes events. It lists
``RECEIVED`` events older than ``--minutes`` and exits non-zero when any are
found, so it can be run in a cron check that pages an operator to re-deliver
the upstream callback (or clear the error that keeps crashing the handler).

Usage::

    python scripts/reconcile_payment_events.py --minutes 30

Backed by the same ``CHAMACORE_DATABASE_URL`` the API is configured with.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.payment_intent import PaymentIntentService
from app.services.payment_webhook import PaymentWebhookService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="report RECEIVED events older than this many minutes (default 30)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="maximum number of events to report (default 100)",
    )
    args = parser.parse_args(argv)

    get_settings()
    older_than = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    db = SessionLocal()
    try:
        events = PaymentWebhookService(db).list_stale_events(
            older_than=older_than, limit=args.limit
        )
        PaymentIntentService(db).refresh_processing_gauge()
    finally:
        db.close()

    if not events:
        print(f"no RECEIVED events older than {args.minutes} minutes")
        return 0

    for event in events:
        received_at = event.received_at.isoformat() if event.received_at else "unknown"
        print(
            f"{received_at}  event_id={event.id}  "
            f"provider_event_id={event.provider_event_id!r}  "
            f"connection_id={event.connection_id}  "
            f"status={event.status.value}"
        )
    print(
        f"found {len(events)} RECEIVED event(s) older than {args.minutes} minutes; "
        "re-deliver the upstream callbacks so the inbox can resume them",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())