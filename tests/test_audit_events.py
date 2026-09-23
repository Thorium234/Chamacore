"""Audit event system tests (ADR-023): recording, listing, append-only invariants."""

import uuid

import pytest
from sqlalchemy import delete, select, update

from app.models.audit_event import AuditEvent
from tests.conftest import add_membership, create_chama, register_and_login


class TestAuditEvents:
    def test_actions_are_recorded_and_listed(self, client, db):
        chair = register_and_login(client, "chair-audit@e.com")
        bob = add_membership(client, chair, create_chama(client, chair)["id"])
        chama_id = bob["chama_id"]

        r = client.get(f"/api/v1/chamas/{chama_id}/audit-events", headers=chair)
        assert r.status_code == 200
        actions = [e["action"] for e in r.json()]
        assert "chama.create" in actions
        assert "membership.create" in actions

    def test_outsider_cannot_list_audit_events(self, client):
        chair = register_and_login(client, "chair-audit2@e.com")
        chama = create_chama(client, chair)
        outsider = register_and_login(client, "outsider-audit@e.com")
        r = client.get(f"/api/v1/chamas/{chama['id']}/audit-events", headers=outsider)
        assert r.status_code == 403

    def test_audit_payload_is_retrievable(self, client):
        chair = register_and_login(client, "chair-audit3@e.com")
        chama = create_chama(client, chair, name="Audited Chama")
        r = client.get(f"/api/v1/chamas/{chama['id']}/audit-events", headers=chair)
        assert r.status_code == 200
        events = [e for e in r.json() if e["action"] == "chama.create"]
        assert len(events) == 1
        assert events[0]["payload"]["name"] == "Audited Chama"
        assert events[0]["success"] is True
        assert events[0]["actor_user_id"] is not None

    def test_login_failure_is_audited(self, client, db):
        _ = register_and_login(client, "target-login@e.com", password="right-pass")
        r = client.post("/api/v1/auth/token", data={"username": "target-login@e.com", "password": "wrong-pass"})
        assert r.status_code == 401
        chair = register_and_login(client, "chair-audit4@e.com")
        chama = create_chama(client, chair)
        # auth events are chama-scoped only when a chama exists; login has no chama,
        # so assert the failed login still produced an immutable event row
        failed = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login_failed")))
        assert len(failed) >= 1
        assert failed[-1].success is False

    def test_audit_events_are_append_only(self, client, db):
        chair = register_and_login(client, "chair-audit5@e.com")
        chama = create_chama(client, chair)
        r = client.get(f"/api/v1/chamas/{chama['id']}/audit-events", headers=chair)
        event_id = r.json()[0]["id"]

        with pytest.raises(Exception):
            db.execute(update(AuditEvent).where(AuditEvent.id == uuid.UUID(event_id)).values(action="tampered"))
            db.commit()

        with pytest.raises(Exception):
            db.execute(delete(AuditEvent).where(AuditEvent.id == uuid.UUID(event_id)))
            db.commit()

        db.rollback()
        r = client.get(f"/api/v1/chamas/{chama['id']}/audit-events", headers=chair)
        assert any(e["id"] == event_id for e in r.json())