# Shared Expenses (Task 6)

A client–server app for shared expenses: groups, expenses with multiple split types, balances, debt simplification, settlements with confirmation, activity feed, debtor reminders (stub email), and group closing with a final report.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2, JWT auth, APScheduler
- **Frontend:** Vue 3 + Vite + TypeScript + Pinia + Vue Router
- **DB:** SQLite by default (fast local run); PostgreSQL via `docker compose`

## Cent leftover rule (equal split)

Amounts are stored in integer cents. For equal splits:

1. `base = total // n`, `remainder = total % n`
2. Participants are sorted by `user_id` ascending
3. The first `remainder` participants get `base + 1`, the rest get `base`

Split parts always sum to the expense total.

## Local run (without Docker)

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
python scripts/seed.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API: http://127.0.0.1:8000/api/health  
Docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173

### Google Sign-In (optional)

Email/password auth always works. To enable **Continue with Google**:

1. In [Google Cloud Console](https://console.cloud.google.com/) create an OAuth client of type **Web application**.
2. Under **Authorized JavaScript origins**, add `http://localhost:5173` and `http://127.0.0.1:5173`.
3. Set the same client ID in both places:

```bash
# backend/.env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

# frontend/.env
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

4. Restart API and Vite. The Google button appears on the login/register page. Without these env vars, the button is hidden.

### Demo users (after seed)

| Email | Password |
|-------|----------|
| alice@example.com | password123 |
| bob@example.com | password123 |
| cara@example.com | password123 |

## Run with PostgreSQL (Docker)

```bash
docker compose up --build
cd frontend && npm install && npm run dev
```

`DATABASE_URL` for the API in compose points at PostgreSQL. Without Docker, the app uses the SQLite file `backend/expenses.db`.

## What works

- Registration / login (JWT), optional Google Sign-In (GIS ID token)
- Groups: create, members, invite by link and email (stub), close/reopen; one currency per group (selector + locale suggestion)
- Expenses: equal / shares / exact, category, date, comment, receipt file
- Balances per group and across all groups; suggested transfers (greedy)
- Settlements: pending → confirm/reject by recipient; only confirmed affect balances
- Activity feed and notifications
- WebSocket updates for balances/feed with two browser tabs open
- Reminder job: emails written to `backend/mail_outbox/` at most once per week
- On group close — final report emailed (stub) to all members
- Unit tests: split, balances/settlements, security, mail stub, API flows — `cd backend && python -m pytest`

## Out of scope / next steps

- Real SMTP and object storage for receipts
- FX rates / multiple currencies inside a single group (each group has one currency)
- Expense edit UI (API `PATCH /api/expenses/{id}` already exists)
- Alembic migrations instead of `create_all` for production
- Richer mobile layout / PWA

## Honest status

The project demonstrates the full Task 6 happy path on SQLite locally. Docker Compose is set up for PostgreSQL; if Docker is unavailable on the machine, use the SQLite mode above. External email is emulated with files in `backend/mail_outbox/`.

## How it was built

Cursor agent + Composer. Reasons: fast FastAPI/Vue scaffolding, iterating on business rules (cents, settlements, WS), easy local run without heavy infrastructure.

See also [DECISION_LOG.md](DECISION_LOG.md).
