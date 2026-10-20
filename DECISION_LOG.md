# Decision log — Shared Expenses

Timestamps in local time (UTC+4), 2026-10-19–20.

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
| 2026-10-20 | Google Sign-In; one currency per group + selector; clearer split types |
| 2026-10-20 | Production pass: expense edit UI, Alembic, SMTP, cookies/refresh, authz, Compose web+CI |

## Key decisions

1. **SQLite by default, Postgres via compose** — fast local run; Postgres is the production DB in Compose.
2. **Balances as derived state** — nets from expenses + confirmed settlements; no debt cache table.
3. **Cents + deterministic leftover rule** — equal split leftover by ascending `user_id`.
4. **Debt simplification = greedy** — classic debtor/creditor matching; `sum(nets) == 0`.
5. **Settlements need recipient confirm** — only `confirmed` affect balances; amount capped to suggested debt.
6. **Email: stub or SMTP** — filesystem outbox for demos; real SMTP via env for production.
7. **WebSocket per group** — broadcast `balances_updated` after mutations.
8. **Auth: JWT access + refresh cookies** — httpOnly cookies (Bearer still accepted); Google GIS ID tokens with password-gated account linking.
9. **One currency per group** — curated ISO allowlist; display-only currency changes (no FX).
10. **Expense mutations** — payer, creator (`created_by_id`), or group owner only.
11. **Receipts** — authenticated download endpoint; public `/uploads` mount removed; 5MB + type allowlist.
12. **Alembic** — `python -m app.bootstrap` / Docker CMD runs `alembic upgrade head` instead of ad-hoc `create_all`.
13. **Compose** — `db` + `api` + `web` (nginx SPA); secrets from `.env` (no hardcoded production secrets).

## Packages (why)

- FastAPI — typed APIs, OpenAPI, WebSockets
- SQLAlchemy 2 + Alembic — ORM + real migrations
- Vue 3 + Pinia + Vue Router — frontend stack from the brief
- APScheduler — periodic reminder emails
- passlib/bcrypt + python-jose — JWT stack
- google-auth + requests — verify Google ID tokens

## Not done (intentionally)

- S3 / object storage for receipts
- Password set/reset UI for Google-only users
- Full HA / multi-region / CDN
