"""Activate Daraja C2B (manual Paybill) callbacks via the ChamaCore API.

This is the C2B "Register URL" step from
``reports/Mpesa_Integration_Validation_Report.md``. It asks the API to
register the Chama's Paybill shortcode with Safaricom, binding the C2B
Validation and Confirmation URLs (each carrying the per-connection callback
token, ADR-018).

The API performs the registration server-side, so this script only needs
chairperson login credentials (never the credential encryption key).

Usage::

    CHAMACORE_EMAIL=chair@example.com CHAMACORE_PASSWORD='***' \\
    CHAMACORE_CHAMA_ID=<uuid> . ./.env \\
    python scripts/register_daraja_c2b_urls.py --connection-id <uuid> [--response-type Cancelled]

Environment variables:

- ``CHAMACORE_BASE_URL``        base URL of the running API (default ``http://localhost:8000``)
- ``CHAMACORE_API_V1_PREFIX``   API prefix (default ``/api/v1``)
- ``CHAMACORE_EMAIL`` / ``CHAMACORE_PASSWORD``   chairperson login credentials
- ``CHAMACORE_CHAMA_ID``        target Chama (or pass ``--chama-id``)

Run AFTER creating (and ideally validating) the payment connection and after
``CHAMACORE_PUBLIC_BASE_URL`` points at the server's public HTTPS URL. Until
the reference-matching rule is approved (OQ-021) the C2B Validation URL
rejects every payment and confirmation never posts to the ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"error: environment variable {name} is required", file=sys.stderr)
        sys.exit(2)
    return value


def _request_json(method: str, url: str, *, payload=None, headers=None, form: bool = False):
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        if form:
            data = urllib.parse.urlencode(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(
            f"error: {method} {url} returned {exc.code}\n{body[:2000]}",
            file=sys.stderr,
        )
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-id", required=True, help="payment connection UUID")
    parser.add_argument(
        "--chama-id",
        default=os.environ.get("CHAMACORE_CHAMA_ID", ""),
        help="target Chama UUID (or set CHAMACORE_CHAMA_ID)",
    )
    parser.add_argument(
        "--response-type",
        choices=["Completed", "Cancelled"],
        default="Completed",
        help="Safaricom ResponseType for the Register URL call",
    )
    args = parser.parse_args(argv)

    try:
        connection_id = uuid.UUID(args.connection_id)
    except ValueError:
        print("error: --connection-id must be a valid UUID", file=sys.stderr)
        return 2

    chama_id = args.chama_id.strip()
    if not chama_id:
        print("error: --chama-id (or CHAMACORE_CHAMA_ID) is required", file=sys.stderr)
        return 2

    email = _require_env("CHAMACORE_EMAIL")
    password = _require_env("CHAMACORE_PASSWORD")
    base_url = os.environ.get("CHAMACORE_BASE_URL", "http://localhost:8000").rstrip("/")
    prefix = os.environ.get("CHAMACORE_API_V1_PREFIX", "/api/v1").strip("/")

    token = _request_json(
        "POST",
        f"{base_url}/{prefix}/auth/token",
        form=True,
        payload={
            "grant_type": "password",
            "username": email,
            "password": password,
            "scope": "",
        },
    ).get("access_token")
    if not token:
        print("error: auth token endpoint returned no access_token", file=sys.stderr)
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    result = _request_json(
        "POST",
        f"{base_url}/{prefix}/chamas/{chama_id}/"
        f"payment-connections/{connection_id}/register-c2b-urls",
        payload={"response_type": args.response_type},
        headers=auth,
    )
    print(
        f"registered C2B URLs (accepted={result['accepted']} "
        f"response={result['response_code']} {result['response_description']})"
    )
    print(f"validation URL:  {result['validation_url']}")
    print(f"confirmation URL:{result['confirmation_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())