"""Observability tests for the payment metrics added by docs/14 (P2#3)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.metrics import (
    REGISTRY,
    Gauge,
    payment_events_stale_received,
    payment_intents_processing,
    payment_validation_total,
)
from app.models import (
    Chama,
    Member,
    Membership,
    PaymentConnection,
    PaymentEvent,
    PaymentIntent,
    User,
)
from app.models.enums import (
    MembershipStatus,
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentIntentStatus,
    PaymentProviderCode,
)
from app.services.payment_intent import PaymentIntentService
from app.services.payment_webhook import PaymentWebhookService

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


class TestGauge:
    @staticmethod
    def _value_lines(render: str, name: str) -> list[str]:
        return [line for line in render.splitlines() if line.startswith(name + " ")]

    def test_set_inc_dec_and_reset(self):
        g = REGISTRY.gauge("chamacore_test_gauge_un", "test")
        assert not self._value_lines(REGISTRY.render(), "chamacore_test_gauge_un")
        g.set(3)
        render = REGISTRY.render()
        assert "# TYPE chamacore_test_gauge_un gauge" in render
        assert "chamacore_test_gauge_un 3" in self._value_lines(render, "chamacore_test_gauge_un")
        g.inc(amount=2)
        assert "chamacore_test_gauge_un 5" in self._value_lines(
            REGISTRY.render(), "chamacore_test_gauge_un"
        )
        g.dec()
        assert "chamacore_test_gauge_un 4" in self._value_lines(
            REGISTRY.render(), "chamacore_test_gauge_un"
        )
        g.reset()
        assert not self._value_lines(REGISTRY.render(), "chamacore_test_gauge_un")

    def test_bounded_labels_render(self):
        g = REGISTRY.gauge("chamacore_test_gauge_lbl", "test", ("provider", "outcome"))
        g.set(1, ("DARAJA", "TIMEOUT"))
        assert (
            'chamacore_test_gauge_lbl{provider="DARAJA",outcome="TIMEOUT"} 1'
            in REGISTRY.render()
        )

    def test_raw_gauge_class_smoke(self):
        g = Gauge("chamacore_test_gauge_raw", "test", ("kind",))
        g.set(2, ("a",))
        g.inc(label_values=("a",))
        assert 'chamacore_test_gauge_raw{kind="a"} 3' in g.lines()


def _seed_payment_connection(db, user):
    chama = Chama(
        name="Metrics Chama", registration_fee_amount=Decimal("100.00"), created_by_user_id=user.id
    )
    db.add(chama)
    db.flush()
    member = Member(
        first_name="Met", last_name="Ric", phone_number="+254000001001", government_id="GID-MET"
    )
    db.add(member)
    db.flush()
    db.add(
        Membership(
            chama_id=chama.id,
            member_id=member.id,
            membership_number=1,
            status=MembershipStatus.ACTIVE,
        )
    )
    conn = PaymentConnection(
        chama_id=chama.id,
        provider_code=PaymentProviderCode.DARAJA,
        environment=PaymentEnvironment.SANDBOX,
        status=PaymentConnectionStatus.ACTIVE,
        encrypted_credentials="sealed",
        masked_account_identifier="6000",
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(conn)
    db.flush()
    return chama, member, conn


class TestReconcileGauges:
    def test_list_stale_events_sets_stale_gauge(self, db):
        user = User(email="metrics@test.local", password_hash="x")
        db.add(user)
        db.flush()
        _, member, conn = _seed_payment_connection(db, user)
        db.add(
            PaymentEvent(
                connection_id=conn.id,
                provider_code=conn.provider_code,
                environment=conn.environment,
                provider_event_id="EVT-STALE",
                payload_hash="digest",
                raw_payload="{}",
                status=PaymentEventStatus.RECEIVED,
                received_at=T0 - timedelta(days=1),
                last_transition_source="PROVIDER_CALLBACK",
            )
        )
        db.commit()

        service = PaymentWebhookService(db)
        events = service.list_stale_events(older_than=datetime.now(timezone.utc) - timedelta(minutes=1))
        assert [e.provider_event_id for e in events] == ["EVT-STALE"]
        assert "chamacore_payment_events_stale_received 1" in REGISTRY.render()
        assert payment_events_stale_received is not None

    def test_refresh_processing_gauge(self, db):
        user = User(email="processing@test.local", password_hash="x")
        db.add(user)
        db.flush()
        chama, member, conn = _seed_payment_connection(db, user)
        ms = db.scalars(
            select(Membership).where(Membership.chama_id == chama.id)
        ).first()
        db.add(
            PaymentIntent(
                chama_id=chama.id,
                membership_id=ms.id,
                amount=Decimal("50.00"),
                currency="KES",
                purpose="contribution",
                status=PaymentIntentStatus.PROCESSING,
                idempotency_key="proc-1",
                idempotency_payload_hash="x",
                created_by_user_id=user.id,
            )
        )
        db.commit()

        PaymentIntentService(db).refresh_processing_gauge()
        assert "chamacore_payment_intents_processing 1" in REGISTRY.render()
        assert payment_intents_processing is not None


class TestMetricsEndpoint:
    def test_payment_metrics_exposed(self, client, db):
        user = User(email="metrics-endpoint@test.local", password_hash="x")
        db.add(user)
        db.flush()
        _, _, conn = _seed_payment_connection(db, user)
        db.add(
            PaymentEvent(
                connection_id=conn.id,
                provider_code=conn.provider_code,
                environment=conn.environment,
                provider_event_id="EVT-MET",
                payload_hash="digest",
                raw_payload="{}",
                status=PaymentEventStatus.RECEIVED,
                received_at=T0 - timedelta(days=1),
                last_transition_source="PROVIDER_CALLBACK",
            )
        )
        db.commit()
        PaymentWebhookService(db).list_stale_events(
            older_than=datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        r = client.get("/metrics")
        assert r.status_code == 200
        assert "chamacore_payment_events_stale_received 1" in r.text
        assert "chamacore_payment_webhook_events_total" in r.text
        assert "chamacore_payment_intents_processing" in r.text
        assert "chamacore_payment_settlement_seconds" in r.text
        assert "chamacore_payment_validation_total" in r.text


class TestValidationCounter:
    def test_counter_metric_registered(self):
        assert payment_validation_total is not None
        assert (
            "# TYPE chamacore_payment_validation_total counter"
            in REGISTRY.render()
        )
