"""Registration-fee payment settlement tests (ADR-022)."""

import uuid

import pytest

from tests.conftest import register_and_login

PERIOD = "2026-12"


def _chair_owned_chama(client, *, fee="250.00"):
    from tests.conftest import create_chama

    chair = register_and_login(client, "chair-fee@e.com")
    chama = create_chama(client, chair, fee=fee)
    return chair, chama


def _add_member(client, chair, chama_id, *, phone="+254700001199", govt="GID-1199", first="Carol", last="Njeri"):
    r = client.post(
        f"/api/v1/chamas/{chama_id}/memberships",
        headers=chair,
        json={"member": {"first_name": first, "last_name": last, "phone_number": phone, "government_id": govt}},
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _fee_status(client, headers, chama_id, membership_id):
    r = client.get(f"/api/v1/chamas/{chama_id}/memberships/{membership_id}/registration-fee", headers=headers)
    assert r.status_code == 200
    return r.json()


def _balances(client, headers, chama_id):
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200
    return {item["code"]: item["balance"] for item in r.json()["items"]}


class TestRegistrationFeeSettlement:
    def test_payment_posts_to_cash_and_registration_fees(self, client):
        chair, chama = _chair_owned_chama(client, fee="250.00")
        member = _add_member(client, chair, chama["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay",
            headers=chair,
        )
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "PAID"
        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "250.00"
        assert bal["4000"] == "-250.00"

    def test_payment_is_idempotent(self, client):
        chair, chama = _chair_owned_chama(client, fee="250.00")
        member = _add_member(client, chair, chama["id"])
        endpoint = f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay"
        r1 = client.post(endpoint, headers=chair)
        assert r1.status_code == 200
        r2 = client.post(endpoint, headers=chair)
        assert r2.status_code == 200
        assert _balances(client, chair, chama["id"])["1000"] == "250.00"
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/payments",
            headers=chair,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_reverse_payment_restores_owed_and_reverses_ledger(self, client):
        chair, chama = _chair_owned_chama(client, fee="300.00")
        member = _add_member(client, chair, chama["id"])
        endpoint = f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay"
        client.post(endpoint, headers=chair)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/payment/reverse",
            headers=chair,
        )
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "OWED"
        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "0.00"
        assert bal["4000"] == "0.00"

    def test_fee_cannot_be_paid_twice_after_reverse_repay(self, client):
        chair, chama = _chair_owned_chama(client, fee="300.00")
        member = _add_member(client, chair, chama["id"])
        pay = f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay"
        reverse = f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/payment/reverse"
        client.post(pay, headers=chair)
        client.post(reverse, headers=chair)
        # re-pay after reversal is allowed and creates a fresh confirmed payment
        r = client.post(pay, headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "PAID"
        assert _balances(client, chair, chama["id"])["1000"] == "300.00"
        # reversing the second payment restores OWED and the ledger
        r = client.post(reverse, headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "OWED"
        assert _balances(client, chair, chama["id"])["1000"] == "0.00"
        # a third reversal finds no confirmed payment
        r = client.post(reverse, headers=chair)
        assert r.status_code == 400
        assert "PAID" in r.json()["detail"]["message"]
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/payments",
            headers=chair,
        )
        assert len(r.json()) == 2

    def test_member_cannot_pay_registration_fee(self, client):
        chair, chama = _chair_owned_chama(client, fee="250.00")
        member = _add_member(client, chair, chama["id"])
        outsider = register_and_login(client, "outsider-fee@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay",
            headers=outsider,
        )
        assert r.status_code == 403

    def test_waived_fee_cannot_be_paid(self, client):
        chair, chama = _chair_owned_chama(client, fee="250.00")
        member = _add_member(client, chair, chama["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/waive",
            headers=chair,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "WAIVED"
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay",
            headers=chair,
        )
        assert r.status_code == 400
        assert "OWED" in r.json()["detail"]["message"]

    def test_payment_list_contains_single_payment(self, client):
        chair, chama = _chair_owned_chama(client, fee="250.00")
        member = _add_member(client, chair, chama["id"])
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/pay",
            headers=chair,
        )
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/registration-fee/payments",
            headers=chair,
        )
        assert r.status_code == 200
        payments = r.json()
        assert len(payments) == 1
        assert payments[0]["status"] == "CONFIRMED"
        assert payments[0]["amount"] == "250.00"