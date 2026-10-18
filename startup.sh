#!/usr/bin/env bash
# Azure App Service / container entrypoint: schema first, then the API.
set -euo pipefail
cd "$(dirname "$0")"
python -m alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
