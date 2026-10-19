from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, SessionLocal, engine
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
    Base.metadata.create_all(bind=engine)
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

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/groups/{group_id}")
async def group_ws(websocket: WebSocket, group_id: int) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    user_id = decode_token(token)
    if user_id is None:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            await websocket.close(code=4401)
            return
        try:
            get_membership(db, group_id, user.id)
        except HTTPException:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    await manager.connect(group_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(group_id, websocket)
