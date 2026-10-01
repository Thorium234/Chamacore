```markdown
# ChamaCore — Delete and re-initialize the SQLite database

Use this when you want a **clean local database** (all users, chamas, payments gone).

Your app uses:

```env
CHAMACORE_DATABASE_URL=sqlite:///./chamacore.db
```

The file `chamacore.db` lives in the **backend project root** (the folder where you run `uvicorn` and `alembic`).

**Important:** Starting uvicorn does **not** create tables. After deleting the DB you must run:

```bash
alembic upgrade head
```

---

## Prerequisites

- Backend repo open (example paths below)
- Virtual environment activated
- Dependencies installed (`pip install -r requirements.txt`)
- You are in the **project root** (where `alembic.ini` and `app/` exist)

---

## Windows (PowerShell)

### 1. Go to the project root

```powershell
cd C:\Users\user\Desktop\programming\pybased\chamacore
```

(Adjust the path if your clone is elsewhere.)

### 2. Activate the virtual environment

```powershell
# If venv is inside the project:
.\.venv\Scripts\Activate.ps1

# If venv is one level up (common layout):
..\ .venv\Scripts\Activate.ps1
```

If execution policy blocks scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

### 3. Stop the API if it is running

In the terminal where uvicorn is running: **Ctrl+C**.

Do not delete the DB while uvicorn is still running (file lock).

### 4. Delete the SQLite files

```powershell
Remove-Item .\chamacore.db -ErrorAction SilentlyContinue
Remove-Item .\chamacore.db-wal -ErrorAction SilentlyContinue
Remove-Item .\chamacore.db-shm -ErrorAction SilentlyContinue
```

Confirm they are gone:

```powershell
Get-ChildItem .\chamacore.db* -ErrorAction SilentlyContinue
```

(No output = deleted.)

### 5. Recreate all tables (migrations)

```powershell
alembic upgrade head
```

You should see Alembic apply revisions until `head`.  
If this fails, fix the error before starting the server (empty DB = `no such table: users`).

### 6. Start the API

```powershell
uvicorn app.main:app --reload
```

Server should listen on `http://127.0.0.1:8000`.

### 7. Clear the frontend browser state

The UI may still hold old JWT tokens and Chama IDs.

On `http://localhost:3000`, open DevTools → Console:

```javascript
localStorage.clear();
sessionStorage.clear();
```

Then hard-refresh the page (Ctrl+Shift+R).

### 8. Create a new account

- Open `/register` (or your register page)
- Register a **new** user — previous users no longer exist
- Log in
- Create a new Chama
- Create a payment connection again if you need Daraja/STK

---

## Linux / macOS (bash)

### 1. Go to the project root

```bash
cd ~/path/to/chamacore
```

### 2. Activate the virtual environment

```bash
source .venv/bin/activate
# or:
source venv/bin/activate
```

### 3. Stop the API if it is running

**Ctrl+C** in the uvicorn terminal.

### 4. Delete the SQLite files

```bash
rm -f chamacore.db chamacore.db-wal chamacore.db-shm
```

Confirm:

```bash
ls chamacore.db* 2>/dev/null || echo "DB files removed"
```

### 5. Recreate all tables (migrations)

```bash
alembic upgrade head
```

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

### 7. Clear the frontend browser state

Same as Windows — in the browser console on the frontend origin:

```javascript
localStorage.clear();
sessionStorage.clear();
```

Hard-refresh, then register and log in again.

---

## One-shot summaries

### Windows (PowerShell) — after stopping uvicorn

```powershell
cd C:\Users\user\Desktop\programming\pybased\chamacore
.\.venv\Scripts\Activate.ps1
Remove-Item .\chamacore.db, .\chamacore.db-wal, .\chamacore.db-shm -ErrorAction SilentlyContinue
alembic upgrade head
uvicorn app.main:app --reload
```

### Linux / macOS — after stopping uvicorn

```bash
cd ~/path/to/chamacore
source .venv/bin/activate
rm -f chamacore.db chamacore.db-wal chamacore.db-shm
alembic upgrade head
uvicorn app.main:app --reload
```

Then clear browser `localStorage` / `sessionStorage` and register a new user.

---

## Troubleshooting

| Symptom | Cause | Fix |
|--------|--------|-----|
| `no such table: users` | DB deleted but migrations not run | `alembic upgrade head` then restart uvicorn |
| `database is locked` | uvicorn still running | Stop uvicorn, delete again, migrate, start |
| Login fails for old email | Users were wiped | Register again |
| “Chama is no longer available” | Frontend still has old Chama UUID | `localStorage.clear()` then create a new Chama |
| `alembic: command not found` | venv not active or package missing | Activate venv; `pip install -r requirements.txt` |
| Wrong folder | Not in project root | `cd` to folder that contains `alembic.ini` |

---

## What is preserved / not preserved

| Item | After reset |
|------|-------------|
| `.env` (JWT secret, Daraja keys, CORS, etc.) | **Kept** |
| Source code | **Kept** |
| All DB rows (users, chamas, ledger, payments) | **Deleted** |
| Payment connections in DB | **Deleted** — recreate via API/UI/script |
| Frontend tokens / known Chama IDs | **Clear manually** in the browser |

---

## Optional: check migration status

```bash
alembic current
alembic history
```

After a successful reset, `alembic current` should report the latest revision (`head`).
```

In the curent folder full list
cd C:\Users\user\Desktop\programming\pybased\chamacore
Remove-Item .\chamacore.db -ErrorAction SilentlyContinue
# optional extras if they exist:
Remove-Item .\chamacore.db-wal -ErrorAction SilentlyContinue
Remove-Item .\chamacore.db-shm -ErrorAction SilentlyContinue
