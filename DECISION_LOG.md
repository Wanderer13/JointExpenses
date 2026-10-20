# Decision log — Shared Expenses

Timestamps in local time (UTC+4), 2026-10-19.

## Timeline

| Time | Event |
|------|--------|
| 17:28 | Read MadDevs materials: assignment PDF, `_data.txt`; chose Task 6 |
| 17:49 | Approved plan: FastAPI + Vue 3 + PostgreSQL/SQLite, JWT, WebSocket, stub mail |
| 17:50 | Started implementation: backend scaffold, docker-compose, models and services |
| 17:52 | Routers for auth/groups/expenses/balances/settlements/activity/notifications + WS |
| 17:54 | Installed Node.js LTS (was missing); scaffolded Vue manually |
| 17:56 | Vue UI: login, groups, group detail (tabs), balances, notifications, join |
| 17:58 | `pytest` passed; seed demo users; README / this log |

## Key decisions

1. **SQLite by default, Postgres via compose** — Docker was unavailable on the dev machine; SQLite meets the “fast local run” requirement, Postgres remains the target option in compose.
2. **Balances as derived state** — nets are computed from expenses + confirmed settlements; no debt cache table → expense edit/delete stays consistent with settlements.
3. **Cents + deterministic leftover rule** — equal split: leftover cents go to the first participants by ascending `user_id` (see README).
4. **Debt simplification = greedy** — classic debtor/creditor matching; enough for the demo and the `sum(nets) == 0` invariant.
5. **Settlements need recipient confirm** — pending ones are visible; only `confirmed` affect balances.
6. **Email stub to filesystem** — `backend/mail_outbox/*.json` instead of SMTP (allowed by the assignment).
7. **WebSocket per group** — for two tabs; broadcast `balances_updated` after mutations.
8. **Auth: JWT login/password + optional Google** — email/password remains the default; Google Sign-In added via GIS ID tokens (`POST /api/auth/google`), not a full OAuth redirect.

## Packages (why)

- FastAPI — typed APIs, OpenAPI, WebSockets out of the box
- SQLAlchemy 2 — ORM + simple `create_all` for the demo
- Vue 3 + Pinia + Vue Router — frontend stack required by the brief
- APScheduler — periodic reminder emails
- passlib/bcrypt + python-jose — standard JWT stack
- google-auth + requests — verify Google ID tokens for Sign-In

## Not done (intentionally)

- Real SMTP / S3
- Expense edit UI (API ready)
- Alembic revision chain for production deploys
- Google OAuth authorization-code redirect / “set password” for Google-only users
