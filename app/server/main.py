from __future__ import annotations

import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.server.websocket import manager
from app.server.routes.graph import router as graph_router
from app.server.routes.tasks import router as tasks_router
from app.server.routes.templates import router as templates_router
from app.server.routes.settings import router as settings_router

# Ensure nodes are registered
_ = importlib.import_module("app.nodes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.server.database import get_db
    db = await get_db()
    await db.close()
    yield
    # Shutdown


app = FastAPI(title="TK Hot Copy API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)
app.include_router(tasks_router)
app.include_router(templates_router)
app.include_router(settings_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
