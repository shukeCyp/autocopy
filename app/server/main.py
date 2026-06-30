from __future__ import annotations

import importlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.server.websocket import manager
from app.server.routes.graph import router as graph_router
from app.server.routes.tasks import router as tasks_router
from app.server.routes.templates import router as templates_router
from app.server.routes.settings import router as settings_router
from app.server.routes.files import router as files_router
from app.server.routes.nodes import router as nodes_router

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
app.include_router(files_router)
app.include_router(nodes_router)

# Serve React frontend if built
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")


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


# SPA catch-all — serve frontend for non-API routes (only if dist exists)
if FRONTEND_INDEX.exists():

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React SPA — return index.html for all non-API routes."""
        from fastapi.responses import FileResponse

        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
