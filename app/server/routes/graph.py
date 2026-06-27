from __future__ import annotations

import asyncio
import importlib
import json

from fastapi import APIRouter, HTTPException

from app.pipeline.graph import Graph
from app.pipeline.executor import Executor
from app.pipeline.types import ExecutorEvent

from app.server.database import create_task, update_task, get_task
from app.server.websocket import manager

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Lazy-import nodes to trigger registration
_ = importlib.import_module("app.nodes")


async def _run_graph(task_id: str, graph_json: str):
    """Background task: run the graph and broadcast progress."""
    try:
        graph = Graph.from_json(graph_json)
    except Exception as e:
        await update_task(task_id, status="failed", error=f"invalid graph: {e}")
        await manager.broadcast(task_id, {"type": "graph_error", "error": str(e)})
        return

    await update_task(task_id, status="running", current_step="开始执行")

    async def on_event(event: ExecutorEvent):
        await manager.broadcast(task_id, {
            "type": event.event_type,
            "node_id": event.node_id,
            "data": event.data,
        })

    executor = Executor(progress_callback=on_event)

    try:
        result = await executor.run(graph)
        await update_task(
            task_id,
            status="done",
            current_step="完成",
            result_json=json.dumps(result.to_dict(), ensure_ascii=False),
        )
        await manager.broadcast(task_id, {
            "type": "graph_complete",
            "task_id": task_id,
            "success": result.success,
        })
    except Exception as e:
        await update_task(task_id, status="failed", error=str(e))
        await manager.broadcast(task_id, {
            "type": "graph_error",
            "task_id": task_id,
            "error": str(e),
        })


@router.post("/run")
async def run_graph(body: dict):
    graph_json = body.get("graph_json", "")
    task_name = body.get("task_name", "")

    if not graph_json:
        raise HTTPException(status_code=400, detail="graph_json is required")

    # Validate JSON
    try:
        parsed = json.loads(graph_json) if isinstance(graph_json, str) else graph_json
        graph_json = json.dumps(parsed, ensure_ascii=False) if not isinstance(graph_json, str) else graph_json
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="graph_json is not valid JSON")

    task = await create_task(task_name, graph_json)

    # Run in background
    asyncio.create_task(_run_graph(task["id"], graph_json))

    return {"task_id": task["id"], "status": "pending"}
