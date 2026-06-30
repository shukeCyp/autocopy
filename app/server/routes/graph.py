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

    await update_task(
        task_id,
        status="running",
        current_step="开始执行",
        current_node_id="",
        current_node_label="",
    )

    async def on_event(event: ExecutorEvent):
        if event.event_type == "node_executing" and event.node_id:
            node = graph.nodes.get(event.node_id)
            label = node.label if node else event.node_id
            await update_task(
                task_id,
                status="running",
                current_step=f"运行节点：{label}",
                current_node_id=event.node_id,
                current_node_label=label,
            )
        elif event.event_type == "node_error" and event.node_id:
            node = graph.nodes.get(event.node_id)
            label = node.label if node else event.node_id
            await update_task(
                task_id,
                current_step=f"节点失败：{label}",
                current_node_id=event.node_id,
                current_node_label=label,
            )
        if event.event_type == "graph_complete":
            return
        await manager.broadcast(task_id, {
            "type": event.event_type,
            "node_id": event.node_id,
            "data": event.data,
        })

    executor = Executor(progress_callback=on_event)

    try:
        result = await executor.run(graph)
        error = ""
        if not result.success:
            error = next((r.error for r in result.node_results if r.error), "graph execution failed")

        await update_task(
            task_id,
            status="done" if result.success else "failed",
            current_step="完成" if result.success else "失败",
            result_json=json.dumps(result.to_dict(), ensure_ascii=False),
            error=error,
        )
        await manager.broadcast(task_id, {
            "type": "graph_complete",
            "task_id": task_id,
            "success": result.success,
            "status": "done" if result.success else "failed",
            "error": error,
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
