from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections grouped by task_id."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._history_limit = 200

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(task_id, []).append(websocket)
        for data in self._history.get(task_id, []):
            await websocket.send_text(json.dumps(data, ensure_ascii=False))

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        if task_id in self._connections:
            self._connections[task_id] = [
                ws for ws in self._connections[task_id] if ws != websocket
            ]
            if not self._connections[task_id]:
                del self._connections[task_id]

    async def broadcast(self, task_id: str, data: dict[str, Any]) -> None:
        history = self._history.setdefault(task_id, [])
        history.append(data)
        if len(history) > self._history_limit:
            del history[:len(history) - self._history_limit]

        if task_id not in self._connections:
            return
        message = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self._connections[task_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(task_id, ws)


manager = ConnectionManager()
