# Decision log — Shared Expenses

Timestamps in local time (UTC+4), 2026-10-19.

## Timeline

| Time | Event |
|------|--------|
| 17:28 | Прочитаны материалы MadDevs: PDF заданий, `_data.txt`, выбрано задание 6 |
| 17:49 | Утверждён план: FastAPI + Vue 3 + PostgreSQL/SQLite, JWT, WebSocket, stub mail |
| 17:50 | Старт реализации: каркас backend, docker-compose, модели и сервисы |
| 17:52 | Роутеры auth/groups/expenses/balances/settlements/activity/notifications + WS |
| 17:54 | Установка Node.js LTS (на машине не было), scaffold Vue вручную |
| 17:56 | Vue UI: login, groups, group detail (tabs), balances, notifications, join |
| 17:58 | `pytest` 4 passed; seed demo users; README / этот лог |

## Key decisions

1. **SQLite by default, Postgres via compose** — Docker на машине разработки отсутствовал; SQLite закрывает требование «быстрый локальный запуск», Postgres остаётся целевым вариантом в compose.
2. **Balances as derived state** — nets считаются из expenses + confirmed settlements; нет кэш-таблицы долгов → edit/delete расхода автоматически согласован с погашениями.
3. **Cents + deterministic leftover rule** — equal split: остаток копеек первым участникам по возрастанию `user_id` (см. README).
4. **Debt simplification = greedy** — классическое сведение должников/кредиторов; достаточно для демо и инварианта `sum(nets) == 0`.
5. **Settlements need recipient confirm** — pending видны, на баланс влияют только `confirmed`.
6. **Email stub to filesystem** — `backend/mail_outbox/*.json` вместо SMTP (разрешено заданием).
7. **WebSocket per group** — для двух вкладок; после мутаций broadcast `balances_updated`.
8. **Auth: JWT login/password** — минимально достаточная модель входа без OAuth.

## Packages (why)

- FastAPI — типизированные API, OpenAPI, WS из коробки
- SQLAlchemy 2 — ORM + простой `create_all` для демо
- Vue 3 + Pinia + Vue Router — выбранный стек фронта из требований
- APScheduler — периодические reminder emails
- passlib/bcrypt + python-jose — стандартный JWT-стек

## Not done (intentionally)

- Real SMTP / S3
- Expense edit UI (API ready)
- Alembic revision chain for production deploys
