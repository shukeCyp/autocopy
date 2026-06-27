# Phase 3 — FastAPI 后端 实施计划

> **Goal:** FastAPI 后端, REST API + WebSocket, SQLite 持久化, 可通过 curl 跑 pipeline

**Architecture:** FastAPI + aiosqlite + background task execution. REST for CRUD, WebSocket for progress events.

**Tech Stack:** fastapi, uvicorn, aiosqlite, websockets

## 文件结构

| 文件 | 职责 |
|------|------|
| `app/server/__init__.py` | 空 |
| `app/server/main.py` | FastAPI app, CORS, lifespan (DB init + WS cleanup) |
| `app/server/database.py` | SQLite schema + async helpers |
| `app/server/routes/__init__.py` | Router 汇总 |
| `app/server/routes/graph.py` | POST /api/graph/run |
| `app/server/routes/tasks.py` | GET/PUT tasks |
| `app/server/routes/templates.py` | GET/POST templates |
| `app/server/routes/settings.py` | GET/PUT settings |
| `app/server/websocket.py` | WebSocket 连接管理 + 广播 |
| `tests/test_server/__init__.py` | 空 |
| `tests/test_server/test_api.py` | API 集成测试 (httpx AsyncClient) |
| `tests/test_server/test_database.py` | DB 操作测试 |

## API 设计

```
POST   /api/graph/run          body: {graph_json, task_name?}  → {task_id}
GET    /api/tasks               → [{id, name, status, ...}]
GET    /api/tasks/{id}          → {task detail + graph + node statuses}
DELETE /api/tasks/{id}          → ok
POST   /api/tasks/{id}/rerun    → ok (force rerun)
GET    /api/templates            → [{id, name}]
POST   /api/templates            body: {name, graph_json}  → {template_id}
GET    /api/settings             → {settings dict}
PUT    /api/settings             body: {settings dict}  → ok
GET    /api/nodes/{node_id}/outputs/{filename}  → file download
WS     /ws/{task_id}             → stream ExecutorEvents as JSON
```

## 数据库 (SQLite)

Tables:
- `tasks`: id TEXT PK, name TEXT, status TEXT, graph_json TEXT, current_step TEXT, result_json TEXT, error TEXT, created_at TEXT, updated_at TEXT
- `settings`: key TEXT PK, value TEXT (JSON blob)
- `templates`: id TEXT PK, name TEXT, graph_json TEXT, created_at TEXT

## 执行流程

1. POST /api/graph/run → Graph.from_json → Executor.run in background task
2. Executor.progress_callback → WebSocket broadcast to /ws/{task_id}
3. Each node_done event → update task status in DB + broadcast
4. Graph complete → update task to done/failed in DB + broadcast

## Notes

- No auth for now (local desktop app)
- CORS allow all origins
- Background tasks use asyncio.create_task
- WebSocket connections tracked per task_id
- Task results stored in DB as JSON
