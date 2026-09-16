"""Public provider webhook inbox (ADR-018).

Unauthenticated by design: providers call this endpoint directly. Security is
provided by the per-connection callback token, attempt binding, amount
matching, payload hashing, deduplication, and the provider verification hook
in :class:`PaymentWebhookService`.

The endpoint always acknowledges a successfully stored event so providers do
not retry endlessly; rejected or rate-limited callbacks return 4xx so the
provider re-delivers later.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import PaymentEnvironment, PaymentProviderCode
from app.services.payment_webhook import (
    PaymentWebhookService,
    check_webhook_rate_limit,
)

router = APIRouter(tags=["payments-webhooks"])


@router.post(
    "/payments/webhooks/{provider_code}/{environment}",
    response_model=dict,
)
async def payments_webhook(
    provider_code: PaymentProviderCode,
    environment: PaymentEnvironment,
    request: Request,
    db: Session = Depends(get_db),
):
    client_host = request.client.host if request.client is not None else "unknown"
    check_webhook_rate_limit(f"{provider_code.value}:{environment.value}:{client_host}")
    raw_payload = await request.body()
    event = PaymentWebhookService(db).handle(
        provider_code=provider_code,
        environment=environment,
        raw_payload=raw_payload,
        headers={key: value for key, value in request.headers.items()},
        query_params=dict(request.query_params),
    )
    return {
        "ok": True,
        "event_id": str(event.id),
        "event_status": event.status.value,
    }