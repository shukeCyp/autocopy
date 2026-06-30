from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.server.database import (
    list_templates,
    get_template,
    save_template,
    update_template,
    delete_template,
    upsert_template,
)
from app.server.workflow_templates import (
    get_workflow_template,
    list_workflow_templates,
    upgrade_workflow_graph_json,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def api_list_templates():
    results = {
        template.id: {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "graph_json": template.graph_json,
        }
        for template in list_workflow_templates().values()
    }

    # Saved templates override file templates with the same id.
    for t in await list_templates():
        results[t["id"]] = {
            "id": t["id"],
            "name": t["name"],
            "description": t.get("description", ""),
            "graph_json": upgrade_workflow_graph_json(t["graph_json"]),
            "created_at": t["created_at"],
        }

    return list(results.values())


@router.get("/{template_id}")
async def api_get_template(template_id: str):
    # Saved templates override file templates with the same id.
    t = await get_template(template_id)
    if t is not None:
        return {
            "id": t["id"],
            "name": t["name"],
            "description": t.get("description", ""),
            "graph_json": upgrade_workflow_graph_json(t["graph_json"]),
        }

    template = get_workflow_template(template_id)
    if template is not None:
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "graph_json": template.graph_json,
        }

    raise HTTPException(status_code=404, detail="template not found")


@router.post("")
async def api_save_template(body: dict):
    name = body.get("name", "").strip()
    description = body.get("description", "").strip()
    graph_json = body.get("graph_json", "")
    if not name or not graph_json:
        raise HTTPException(status_code=400, detail="name and graph_json are required")
    graph_json = upgrade_workflow_graph_json(graph_json)
    t = await save_template(name, graph_json, description)
    return {"id": t["id"], "name": t["name"], "description": t.get("description", "")}


@router.put("/{template_id}")
async def api_update_template(template_id: str, body: dict):
    name = body.get("name", "").strip()
    description = body.get("description")
    if isinstance(description, str):
        description = description.strip()
    graph_json = body.get("graph_json", "")
    if not name or not graph_json:
        raise HTTPException(status_code=400, detail="name and graph_json are required")
    graph_json = upgrade_workflow_graph_json(graph_json)

    t = await update_template(template_id, name, graph_json, description)
    if t is None:
        if get_workflow_template(template_id) is None:
            raise HTTPException(status_code=404, detail="template not found")
        t = await upsert_template(template_id, name, graph_json, description or "")
    return {"id": t["id"], "name": t["name"], "description": t.get("description", "")}


@router.delete("/{template_id}")
async def api_delete_template(template_id: str):
    deleted = await delete_template(template_id)
    if get_workflow_template(template_id) is not None:
        return {"ok": True}
    if not deleted:
        raise HTTPException(status_code=404, detail="template not found")
    return {"ok": True}
