# Minimal Daraja-only focus (do not rewrite the payment stack)

## Goal

- Stop exposing Jenga as an active provider.
- Keep Daraja as the only registered provider for new connections.
- Add `.env.example` so sandbox credentials can be pasted and used when creating a connection.
- Touch as few files as possible.

## Important design note

ChamaCore stores provider credentials **per payment connection in the DB** (AES-GCM sealed), not from env on every STK push. That is correct for multi-Chama production.

`.env` is for:
1. App settings (`CHAMACORE_*`)
2. A place to paste your Daraja sandbox values so you can copy them into the **create payment connection** API body (or a small seed script later)

Do **not** hard-code sandbox secrets into the adapter.

## File changes (only these)

### 1. Add `.env.example` (new file)

See the companion `.env.example` in this folder. Copy to project root as `.env` and fill in:

```bash
cp .env.example .env
# edit .env with your Safaricom developer portal values
```

`.gitignore` already ignores `.env` — keep it that way.

### 2. `app/providers/registry.py` — stop registering Jenga

Change `build_default_registry` only:

```python
def build_default_registry() -> ProviderRegistry:
    """Wire supported provider adapters (Daraja only for now)."""
    from app.providers.daraja.adapter import create_daraja_adapters

    registry = ProviderRegistry()
    for adapter in create_daraja_adapters():
        registry.register(adapter)
    return registry
```

Do **not** delete `app/providers/jenga/` yet if you want a one-line rollback. Unregistering is enough to prevent new Jenga connections.

### 3. `app/models/enums.py` — keep `JENGA` enum value

Leave `PaymentProviderCode.JENGA = "JENGA"` in place so existing DB rows (if any) still load. Removing the enum value would force a migration and risk IntegrityError on old data.

### 4. Tests — minimal adjustment

In `tests/test_provider_adapters.py`:

- Keep Daraja tests as-is.
- Either delete or `@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")` the Jenga test classes:
  - `TestJengaAuthentication`
  - `TestJengaPaymentAttempt`
  - and any other `TestJenga*` classes
- Update `TestRegistry.test_jenga_adapters_one_per_environment` similarly, or remove it.
- In `TestRegistry`, remove Jenga from the `test_spec_metadata` parametrize list if it still includes `JengaAdapter`.

Do **not** rewrite the whole test file.

### 5. Optional one-liner in README

Under Implemented / Payment architecture, note:

> Active provider: **Daraja** (sandbox + production). Jenga adapter code is retained but not registered.

## How to test against Safaricom sandbox

1. Fill `.env` with your Daraja consumer key/secret, short code, passkey.
2. Start the API (`uvicorn app.main:app --reload`).
3. Register + login, create a Chama, become chairperson.
4. Create a payment connection via API with body shaped like:

```json
{
  "provider_code": "DARAJA",
  "environment": "SANDBOX",
  "credentials": {
    "consumer_key": "<from .env DARAJA_CONSUMER_KEY>",
    "consumer_secret": "<from .env DARAJA_CONSUMER_SECRET>",
    "short_code": "<from .env DARAJA_SHORT_CODE>",
    "passkey": "<from .env DARAJA_PASSKEY>"
  }
}
```

5. Validate / enable the connection, then create a payment intent and initiate STK Push with a sandbox test phone.

Callbacks from Safaricom need a public URL. For local work, set `CHAMACORE_PUBLIC_BASE_URL` to an ngrok/cloudflared URL pointing at your machine, or rely on status-query polling for sandbox experiments.

## What not to do

- Do not rewrite the payment intent/connection/webhook services.
- Do not move sealed credentials to env for production multi-tenant use.
- Do not remove the `JENGA` enum without a migration plan.
- Do not commit real secrets.
