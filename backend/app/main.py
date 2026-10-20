from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.constants import ACCESS_COOKIE, WS_CLOSE_FORBIDDEN, WS_CLOSE_UNAUTHORIZED
from app.database import SessionLocal, engine
from app.deps import get_membership
from app.routers import activity, auth, balances, expenses, groups, notifications, settlements
from app.security import decode_token, get_user_by_id
from app.services.reminder_service import process_debt_reminders
from app.ws import manager

settings = get_settings()


def _ensure_dirs() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.mail_outbox_dir).mkdir(parents=True, exist_ok=True)


def _run_reminders() -> None:
    db = SessionLocal()
    try:
        process_debt_reminders(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_dirs()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_reminders, "interval", seconds=settings.reminder_check_seconds, id="reminders")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Shared Expenses", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(balances.router, prefix="/api")
app.include_router(settlements.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.websocket("/ws/groups/{group_id}")
async def group_ws(websocket: WebSocket, group_id: int) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get(ACCESS_COOKIE)
    if not token:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    user_id = decode_token(token)
    if user_id is None:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        try:
            get_membership(db, group_id, user.id)
        except HTTPException:
            await websocket.close(code=WS_CLOSE_FORBIDDEN)
            return
    finally:
        db.close()

    await manager.connect(group_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(group_id, websocket)
