"""C2B (manual Paybill money-in) endpoints (ADR-016, C2B).

Unauthenticated by design: Safaricom calls these URLS directly. Binding and
authentication use the per-connection callback token (query parameter) plus
the connection id in the path; the payloads are parsed, stored in the
immutable event inbox, deduplicated by ``TransID``, and (for confirmation)
acknowledged without writing to the ledger.

The Validation endpoint always answers ``ResultCode`` 1 (reject) until the
BillRefNumber-to-member matching rule is decided (OQ-021, OPEN_QUESTIONS.md).
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.payment import C2BConfirmationResponse, C2BValidationResponse
from app.services.c2b_payment import C2BPaymentService, check_c2b_rate_limit

router = APIRouter(tags=["payments-c2b"])


@router.post(
    "/payments/c2b/validate/{connection_id}",
    response_model=C2BValidationResponse,
)
async def c2b_validate_payment(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    client_host = request.client.host if request.client is not None else "unknown"
    check_c2b_rate_limit("validate", client_host)
    raw_payload = await request.body()
    decision = C2BPaymentService(db).validate(
        connection_id=connection_id,
        raw_payload=raw_payload,
        headers={key: value for key, value in request.headers.items()},
        query_params=dict(request.query_params),
    )
    return {
        "ResultCode": decision.result_code,
        "ResultDesc": decision.result_description,
    }


@router.post(
    "/payments/c2b/confirm/{connection_id}",
    response_model=C2BConfirmationResponse,
)
async def c2b_confirm_payment(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    client_host = request.client.host if request.client is not None else "unknown"
    check_c2b_rate_limit("confirm", client_host)
    raw_payload = await request.body()
    event = C2BPaymentService(db).confirm(
        connection_id=connection_id,
        raw_payload=raw_payload,
        headers={key: value for key, value in request.headers.items()},
        query_params=dict(request.query_params),
    )
    return {
        "ok": True,
        "event_id": str(event.id),
        "event_status": event.status.value,
    }