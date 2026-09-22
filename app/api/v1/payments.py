"""Payment connection, intent, and attempt endpoints (ADR-016/017).

Connection management is chairperson-only. Intents and attempts are readable
by any active member of the Chama, and initiation selects an ACTIVE
connection. No endpoint ever returns provider credentials or encrypted
blobs.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.payment import (
    C2BRegisterUrlOut,
    C2BRegisterUrlRequest,
    PaymentAttemptOut,
    PaymentConnectionCreate,
    PaymentConnectionOut,
    PaymentConnectionReplace,
    PaymentIntentCreate,
    PaymentIntentInitiate,
    PaymentIntentOut,
)
from app.services.payment_connection import PaymentConnectionService
from app.services.payment_intent import PaymentIntentService

router = APIRouter(tags=["payments"])


@router.post(
    "/chamas/{chama_id}/payment-connections",
    response_model=PaymentConnectionOut,
    status_code=201,
)
def create_payment_connection(
    payload: PaymentConnectionCreate,
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).create(
        actor=actor,
        chama_id=chama_id,
        provider_code=payload.provider_code,
        environment=payload.environment,
        credentials=payload.credentials,
    )


@router.get(
    "/chamas/{chama_id}/payment-connections",
    response_model=list[PaymentConnectionOut],
)
def list_payment_connections(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).list(actor=actor, chama_id=chama_id)


@router.get(
    "/chamas/{chama_id}/payment-connections/{connection_id}",
    response_model=PaymentConnectionOut,
)
def get_payment_connection(
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).get(
        actor=actor, chama_id=chama_id, connection_id=connection_id
    )


@router.post(
    "/chamas/{chama_id}/payment-connections/{connection_id}/validate",
    response_model=PaymentConnectionOut,
)
def validate_payment_connection(
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).validate(
        actor=actor, chama_id=chama_id, connection_id=connection_id
    )


@router.patch(
    "/chamas/{chama_id}/payment-connections/{connection_id}",
    response_model=PaymentConnectionOut,
)
def replace_payment_connection(
    payload: PaymentConnectionReplace,
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).replace(
        actor=actor,
        chama_id=chama_id,
        connection_id=connection_id,
        credentials=payload.credentials,
    )


@router.post(
    "/chamas/{chama_id}/payment-connections/{connection_id}/disable",
    response_model=PaymentConnectionOut,
)
def disable_payment_connection(
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).disable(
        actor=actor, chama_id=chama_id, connection_id=connection_id
    )


@router.post(
    "/chamas/{chama_id}/payment-connections/{connection_id}/register-c2b-urls",
    response_model=C2BRegisterUrlOut,
)
def register_c2b_urls(
    payload: C2BRegisterUrlRequest,
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentConnectionService(db).register_c2b_urls(
        actor=actor,
        chama_id=chama_id,
        connection_id=connection_id,
        response_type=payload.response_type,
    )


@router.delete(
    "/chamas/{chama_id}/payment-connections/{connection_id}",
    status_code=204,
)
def delete_payment_connection(
    chama_id: uuid.UUID,
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    PaymentConnectionService(db).delete(
        actor=actor, chama_id=chama_id, connection_id=connection_id
    )
    return Response(status_code=204)


@router.post(
    "/chamas/{chama_id}/payment-intents",
    response_model=PaymentIntentOut,
    status_code=201,
)
def create_payment_intent(
    payload: PaymentIntentCreate,
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).create(
        actor=actor,
        chama_id=chama_id,
        membership_id=payload.membership_id,
        amount=payload.amount,
        currency=payload.currency,
        purpose=payload.purpose,
        idempotency_key=payload.idempotency_key,
        contribution_id=payload.contribution_id,
    )


@router.get(
    "/chamas/{chama_id}/payment-intents",
    response_model=list[PaymentIntentOut],
)
def list_payment_intents(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).list_intents(actor=actor, chama_id=chama_id)


@router.get(
    "/chamas/{chama_id}/payment-intents/{intent_id}",
    response_model=PaymentIntentOut,
)
def get_payment_intent(
    chama_id: uuid.UUID,
    intent_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).get_intent(
        actor=actor, chama_id=chama_id, intent_id=intent_id
    )


@router.post(
    "/chamas/{chama_id}/payment-intents/{intent_id}/initiate",
    response_model=PaymentAttemptOut,
)
def initiate_payment_intent(
    payload: PaymentIntentInitiate,
    chama_id: uuid.UUID,
    intent_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).initiate(
        actor=actor,
        chama_id=chama_id,
        intent_id=intent_id,
        connection_id=payload.connection_id,
    )


@router.get(
    "/chamas/{chama_id}/payment-intents/{intent_id}/attempts",
    response_model=list[PaymentAttemptOut],
)
def list_payment_attempts(
    chama_id: uuid.UUID,
    intent_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).list_attempts(
        actor=actor, chama_id=chama_id, intent_id=intent_id
    )


@router.get(
    "/chamas/{chama_id}/payment-attempts/{attempt_id}",
    response_model=PaymentAttemptOut,
)
def get_payment_attempt(
    chama_id: uuid.UUID,
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PaymentIntentService(db).get_attempt(
        actor=actor, chama_id=chama_id, attempt_id=attempt_id
    )