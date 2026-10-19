# Shared Expenses (Задание 6)

Клиент-серверное приложение для совместных расходов: группы, расходы с разными типами деления, балансы, упрощение долгов, погашения с подтверждением, лента активности, напоминания должникам (stub-почта), закрытие группы с итоговым отчётом.

## Стек

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2, JWT auth, APScheduler
- **Frontend:** Vue 3 + Vite + TypeScript + Pinia + Vue Router
- **DB:** SQLite по умолчанию (быстрый локальный запуск); PostgreSQL через `docker compose`

## Правило копеек (equal split)

Суммы хранятся в целых центах. При делении поровну:

1. `base = total // n`, `remainder = total % n`
2. Участники сортируются по `user_id` по возрастанию
3. Первые `remainder` участников получают `base + 1`, остальные — `base`

Сумма долей всегда равна сумме расхода.

## Локальный запуск (без Docker)

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

### Demo users (после seed)

| Email | Password |
|-------|----------|
| alice@example.com | password123 |
| bob@example.com | password123 |
| cara@example.com | password123 |

## Запуск с PostgreSQL (Docker)

```bash
docker compose up --build
cd frontend && npm install && npm run dev
```

Переменная `DATABASE_URL` для API в compose задана на PostgreSQL. Локально без Docker используется SQLite-файл `backend/expenses.db`.

## Что работает

- Регистрация / логин (JWT)
- Группы: создание, участники, invite по ссылке и email (stub), close/reopen
- Расходы: equal / shares / exact, категория, дата, комментарий, файл чека
- Балансы по группе и по всем группам; suggested transfers (greedy)
- Погашения: pending → confirm/reject получателем; в баланс только confirmed
- Лента активности и уведомления
- WebSocket-обновления балансов/ленты при двух открытых вкладках
- Reminder job: письмо в `backend/mail_outbox/` не чаще раза в неделю
- При закрытии группы — итоговый отчёт в stub-почту всем участникам
- Юнит-тесты split/balance: `cd backend && python -m pytest`

## Что не вошло / next steps

- Реальный SMTP и объектное хранилище для чеков
- Курсы валют / мультивалютность внутри группы
- Редактирование расхода в UI (API `PATCH /api/expenses/{id}` уже есть)
- Alembic-миграции вместо `create_all` для продакшена
- Более богатая мобильная вёрстка / PWA

## Честное состояние

Проект демонстрирует полный happy-path задания 6 на SQLite локально. Docker Compose описан для PostgreSQL; на машине разработки Docker может отсутствовать — тогда используйте SQLite-режим выше. Внешняя почта эмулируется файлами в `backend/mail_outbox/`.

## Чем делали

Cursor agent + Composer. Причины: быстрый каркас FastAPI/Vue, итерации по бизнес-правилам (копейки, settlements, WS), удобный локальный прогон без лишней инфраструктуры.

См. также [DECISION_LOG.md](DECISION_LOG.md).
