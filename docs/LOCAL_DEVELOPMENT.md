# ChamaCore Local Development Runbook

**Audience:** Developers, new contributors, QA engineers  
**Covers:** Setting up and running the ChamaCore backend alongside the frontend client.

---

## 1. Prerequisites

- Python 3.12+
- Node.js 20+
- SQLite (built into Python) or PostgreSQL 16+
- Git

---

## 2. Backend Setup (`pybased/chamacore`)

### 2.1 Virtual Environment & Dependencies

```bash
cd pybased/chamacore

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On Linux / macOS:
source .venv/bin/activate

# Install runtime and development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2.2 Environment Configuration

Create a local `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Ensure the following core variables are configured for local development:

```env
CHAMACORE_ENV=development
CHAMACORE_DEBUG=true
CHAMACORE_DATABASE_URL=sqlite:///./chamacore.db
CHAMACORE_JWT_SECRET_KEY=dev-secret-key-change-in-production-min32bytes
CHAMACORE_CREDENTIAL_CIPHER_KEY=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
CHAMACORE_CORS_ORIGINS=["http://localhost:3000"]
CHAMACORE_PAYMENT_PROVIDER_ACTIVE=DARAJA
```

### 2.3 Database Migrations & Initial Setup

```bash
# Apply database migrations
alembic upgrade head

# Bootstrap the first Platform Administrator (optional for dev)
python -m app.db.bootstrap_platform_admin

# Populate sample Chamas and member fixtures (optional)
python scripts/demo_seed.py
```

### 2.4 Running the API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs) (enabled when `CHAMACORE_DEBUG=true`)
- Health endpoint: [http://localhost:8000/health](http://localhost:8000/health)

---

## 3. Frontend Setup (`frontend/chamacore-frontend`)

In a separate terminal:

```bash
cd frontend/chamacore-frontend

# Install node dependencies
npm install

# Configure environment
# Ensure .env.local contains:
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 4. Common Local Failures & Solutions

| Failure | Symptom | Root Cause | Solution |
|---|---|---|---|
| **Invalid Cipher Key** | Crash on startup with `ValueError: Invalid AES key length` | `CHAMACORE_CREDENTIAL_CIPHER_KEY` is missing or not a 32-byte base64 string | Generate a 32-byte key: `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` and put in `.env`. |
| **CORS Blocked** | Browser console shows `CORS policy: No 'Access-Control-Allow-Origin'` | Frontend port (e.g. 3000) not listed in `CHAMACORE_CORS_ORIGINS` | Add `http://localhost:3000` to `CHAMACORE_CORS_ORIGINS` in `.env`. |
| **Database Locked (SQLite)** | `sqlite3.OperationalError: database is locked` | Multiple processes writing to `chamacore.db` concurrently | Use PostgreSQL for multi-worker testing or ensure only one uvicorn worker runs. |
| **STK Webhooks Not Arriving** | STK push completes on phone, but intent stays `PENDING` | Safaricom Daraja cannot reach `localhost` | Run an ngrok tunnel (`ngrok http 8000`) and set `CHAMACORE_PAYMENT_WEBHOOK_BASE_URL=https://<your-ngrok>.ngrok-free.app`. |
