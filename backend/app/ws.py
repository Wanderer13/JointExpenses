from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, group_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms[group_id].add(websocket)

    async def disconnect(self, group_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._rooms[group_id].discard(websocket)
            if not self._rooms[group_id]:
                del self._rooms[group_id]

    async def broadcast(self, group_id: int, message: dict) -> None:
        data = json.dumps(message, default=str)
        async with self._lock:
            sockets = list(self._rooms.get(group_id, set()))
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(group_id, ws)


manager = ConnectionManager()
