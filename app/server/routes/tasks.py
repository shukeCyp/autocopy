from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.server.database import list_tasks, get_task, update_task, delete_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def api_list_tasks():
    return await list_tasks()


@router.get("/{task_id}")
async def api_get_task(task_id: str):
    task = await get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.delete("/{task_id}")
async def api_delete_task(task_id: str):
    deleted = await delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True}


@router.post("/{task_id}/rerun")
async def api_rerun_task(task_id: str):
    import asyncio
    from app.server.routes.graph import _run_graph

    task = await get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    await update_task(
        task_id,
        status="pending",
        error="",
        current_node_id="",
        current_node_label="",
    )
    asyncio.create_task(_run_graph(task_id, task["graph_json"]))
    return {"ok": True, "task_id": task_id}
