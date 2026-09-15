"""Seed a ChamaDemo through the live API like a real user.

Run against a running server (uvicorn app.main:app --reload):

    python scripts/demo_seed.py
    python scripts/demo_seed.py --members 5 --period 2026-09

Touches: register/login (token), chama creation, membership creation,
role assignment, identity claim, fee view/waive, contribution record,
confirm, and share listing.
"""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime

import httpx

BASE_URL = os.environ.get("CHAMACORE_API_URL", "http://127.0.0.1:8000")
TOKEN_FILE = "chamacore_token.txt"


def die(msg: str) -> None:
    raise SystemExit(msg)


def check(resp: httpx.Response, what: str) -> httpx.Response:
    if resp.status_code >= 400:
        die(f"{what} failed [{resp.status_code}]: {resp.text}")
    print(f"  OK {what} -> {resp.status_code}")
    return resp


def register(client: httpx.Client, email: str, password: str) -> dict:
    r = check(
        client.post("/api/v1/auth/register", json={"email": email, "password": password}),
        f"register {email}",
    )
    return r.json()


def login(client: httpx.Client, email: str, password: str) -> dict:
    r = check(
        client.post("/api/v1/auth/token", data={"username": email, "password": password}),
        f"login {email}",
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def claim_member(client: httpx.Client, headers: dict, phone: str, govt: str) -> None:
    check(
        client.post(
            "/api/v1/auth/me/member-link",
            headers=headers,
            json={"phone_number": phone, "government_id": govt},
        ),
        f"claim identity {phone}",
    )


def run(args: argparse.Namespace) -> None:
    print(f"Using API at {BASE_URL}")
    suffix = uuid.uuid4().hex[:6]
    email = f"chair.{suffix}@demo.chama"
    password = "securepass123"
    phone_base = args.phone_base or f"+2547{int(suffix, 16) % 100_000_000:08d}"

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        # 1) Chairperson account
        register(client, email, password)
        chair = login(client, email, password)
        with open(TOKEN_FILE, "w") as f:
            f.write(chair["Authorization"].removeprefix("Bearer "))
        print(f"  saved token -> {TOKEN_FILE}")

        # 2) Create a Chama (creator becomes Chairperson + Member)
        chairman_phone = f"{phone_base}001"
        r = check(
            client.post(
                "/api/v1/chamas",
                headers=chair,
                json={
                    "name": args.name,
                    "registration_fee_amount": "200.00",
                    "description": "Seeded by scripts/demo_seed.py",
                    "member": {
                        "first_name": "Chair",
                        "last_name": "Person",
                        "phone_number": chairman_phone,
                        "government_id": f"GID-001-{suffix}",
                    },
                },
            ),
            "create chama",
        )
        chama = r.json()
        chama_id = chama["id"]
        print(f"  chama_id={chama_id}")

        # 3) Register N members via the chairperson
        member_ids: list[str] = []
        for i in range(args.members):
            phone = f"{phone_base}{i + 2:03d}"
            r = check(
                client.post(
                    f"/api/v1/chamas/{chama_id}/memberships",
                    headers=chair,
                    json={
                        "member": {
                            "first_name": f"Member{i + 1}",
                            "last_name": "Otieno",
                            "phone_number": phone,
                            "government_id": f"GID-{i + 2:03d}-{suffix}",
                        },
                    },
                ),
                f"add member {i + 1}",
            )
            member_ids.append(r.json()["id"])

        # 4) Assign roles: treasurer + secretary
        r = check(
            client.post(
                f"/api/v1/chamas/{chama_id}/memberships/{member_ids[0]}/roles",
                headers=chair,
                json={"role": "TREASURER"},
            ),
            "assign TREASURER",
        )
        sec_member = member_ids[1] if len(member_ids) > 1 else member_ids[0]
        check(
            client.post(
                f"/api/v1/chamas/{chama_id}/memberships/{sec_member}/roles",
                headers=chair,
                json={"role": "SECRETARY"},
            ),
            "assign SECRETARY",
        )

        # 5) View a registration fee, then waive the second member's fee
        check(
            client.get(
                f"/api/v1/chamas/{chama_id}/memberships/{member_ids[0]}/registration-fee",
                headers=chair,
            ),
            "view registration fee",
        )
        if len(member_ids) > 1:
            check(
                client.post(
                    f"/api/v1/chamas/{chama_id}/memberships/{member_ids[1]}/registration-fee/waive",
                    headers=chair,
                ),
                "waive registration fee",
            )

        # 6) Treasurer claims identity and records a contribution as a real user
        treasurer_phone = f"{phone_base}002"
        if len(member_ids) > 1:
            # treasurer is member #1 (member_ids index 0)
            treas_email = f"treasurer.{suffix}@demo.chama"
            register(client, treas_email, password)
            treas = login(client, treas_email, password)
            claim_member(client, treas, treasurer_phone, f"GID-002-{suffix}")
        else:
            treas = chair

        period = args.period
        amounts = [str(round(200.0 + i * 137.5, 2)) for i in range(len(member_ids))]
        recorded_ids: list[str] = []
        for mid, amount in zip(member_ids, amounts, strict=False):
            r = check(
                client.post(
                    f"/api/v1/chamas/{chama_id}/contributions",
                    headers=treas,
                    json={"membership_id": mid, "amount": amount, "period": period},
                ),
                f"record contribution {amount} for period {period}",
            )
            recorded_ids.append(r.json()["id"])

        # 7) Chairperson confirms -> shares are created automatically
        for cid in recorded_ids:
            check(
                client.post(
                    f"/api/v1/chamas/{chama_id}/contributions/{cid}/confirm",
                    headers=chair,
                ),
                f"confirm contribution {cid[:8]}",
            )

        # 8) Read back memberships, contributions, and shares
        check(
            client.get(f"/api/v1/chamas/{chama_id}/memberships", headers=chair),
            "list memberships",
        )
        check(
            client.get(f"/api/v1/chamas/{chama_id}/contributions", headers=chair),
            "list contributions",
        )
        check(
            client.get(
                f"/api/v1/chamas/{chama_id}/memberships/{member_ids[0]}/shares",
                headers=chair,
            ),
            "list shares",
        )

        print(
            "\nDone. Chama:", chama_id,
            "| members:", len(member_ids),
            "| contributions confirmed:", len(recorded_ids),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data through the ChamaCore API")
    parser.add_argument("--name", default="Demo Chama")
    parser.add_argument("--members", type=int, default=4)
    parser.add_argument("--period", default=datetime.now().strftime("%Y-%m"))
    parser.add_argument(
        "--phone-base",
        default=None,
        help="phone prefix (e.g. +2547). Default: unique per run to avoid collisions",
    )
    parser.add_argument("--url", default=None, help="override CHAMACORE_API_URL")
    args = parser.parse_args()
    if args.url:
        os.environ["CHAMACORE_API_URL"] = args.url
    if args.members < 2:
        die("need at least 2 members so treasurer + secretary roles can be assigned")
    run(args)


if __name__ == "__main__":
    main()