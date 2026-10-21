# Shared Expenses (Task 6)

A client–server app for shared expenses: groups, expenses with multiple split types, balances, debt simplification, settlements with confirmation, activity feed, debtor reminders, and group closing with a final report.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, JWT + refresh cookies, APScheduler
- **Frontend:** Vue 3 + Vite + TypeScript + Pinia + Vue Router (nginx in production)
- **DB:** SQLite for local/dev; PostgreSQL via Docker Compose

## Cent leftover rule (equal split)

Amounts are stored in integer cents. For equal splits:

1. `base = total // n`, `remainder = total % n`
2. Participants are sorted by `user_id` ascending
3. The first `remainder` participants get `base + 1`, the rest get `base`

Split parts always sum to the expense total.

## Production run (Docker Compose)

1. Copy [`.env.example`](.env.example) to `.env` and set strong `SECRET_KEY` and `POSTGRES_PASSWORD`.
2. Optionally set `MAIL_BACKEND=smtp` and SMTP_* for real email (default is filesystem stub).
3. Build and start:

```bash
docker compose up --build
```

UI: http://localhost:8080 (or `WEB_PORT`)  
API health (via nginx): http://localhost:8080/api/health

Put a TLS reverse proxy in front of `web` for real HTTPS and set `COOKIE_SECURE=true`.

## Local run (without Docker)

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m app.bootstrap
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
2. Under **Authorized JavaScript origins**, add your UI origins (e.g. `http://localhost:5173`, `http://localhost:8080`).
3. Set the same client ID in both places:

```bash
# Copy from the examples (demo client ID is already filled in):
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Or set the same Web client ID in both files:

```bash
GOOGLE_CLIENT_ID=58304476274-je7ea6s4rc3a7ajl7o0u0hdlgrgdnhju.apps.googleusercontent.com
VITE_GOOGLE_CLIENT_ID=58304476274-je7ea6s4rc3a7ajl7o0u0hdlgrgdnhju.apps.googleusercontent.com
```

Never commit a Google **client secret** (`GOCSPX-…`) — this app only needs the client ID. If Sign-In hits an existing email/password account, enter that password and retry — linking requires password proof.

### Demo users (after seed)

| Email | Password |
|-------|----------|
| alice@example.com | password123 |
| bob@example.com | password123 |
| cara@example.com | password123 |

### Admin (testing)

Set `ADMIN_EMAILS` (comma-separated) in `backend/.env` so those addresses get the `admin` app role on register, Google signup, or seed. Admins can also promote/demote others in the UI.

- Panel: `/admin` (nav link only for admins)
- Clear linked users: deletes all accounts except the seed defaults above (and never deletes the acting admin)
- Action log: auth and mutating API calls are recorded for admins to review

## What works

- Registration / login (JWT in httpOnly cookies + Bearer), refresh/logout, optional Google Sign-In
- App roles (`user` / `admin`), admin panel, clear non-seed users, app-wide action log
- Groups: create, members, invite by link and email (absolute join URL + HTML), auto-join on register/login when email was invited; close/reopen; one currency per group
- Expenses: equal / shares / exact, category, date, comment, receipt; **create / edit / delete** (payer, creator, or owner)
- Balances per group and across all groups; suggested transfers (greedy)
- Settlements: pending → confirm/reject by recipient; amount capped to outstanding debt; only confirmed affect balances
- Home: “Needs you” (pending pays / unpaid) then groups; create group opens People to invite
- Group journey tabs: People → Expenses → Settle → Activity (breadcrumb + checklist); invite link works before register
- Co-member profiles (`/users/:id`) with mailto email; people linked by name
- Activity feed and notifications
- WebSocket updates for balances/feed with two browser tabs open
- Reminder job: SMTP or stub outbox at most once per week
- On group close — final report emailed (SMTP or stub) to all members
- Alembic migrations on API bootstrap; authenticated receipt download; upload size/type limits
- Unit tests + CI: `cd backend && python -m pytest`; frontend `npm run build` (includes `vue-tsc`)

## Mail

- `MAIL_BACKEND=stub` (default): JSON files under `backend/mail_outbox/` (`body`, `body_html`, `meta.join_url`)
- `MAIL_BACKEND=smtp`: real SMTP via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS`
- `FRONTEND_URL`: public UI origin for invite links (default local Vite `http://127.0.0.1:5173`; Compose `http://localhost:8080`)
- After **Invite by email**, the UI also shows the join link (handy for stub). Logging in or registering with that email auto-joins open groups; or open `/join/{token}`

## Out of scope / next steps

- Object storage (S3) for receipts instead of a local volume
- FX rates / multiple currencies inside a single group
- Password set/reset UI for Google-only users
- Richer mobile layout / PWA

## Honest status

Task 6 happy path works locally on SQLite and via Compose (Postgres + API + nginx UI). External email defaults to the stub outbox unless SMTP is configured. Put TLS in front of Compose for production HTTPS.

## How it was built

Cursor agent + Composer. Reasons: fast FastAPI/Vue scaffolding, iterating on business rules (cents, settlements, WS), deployable Compose stack with migrations and cookie auth.

See also [DECISION_LOG.md](DECISION_LOG.md).
