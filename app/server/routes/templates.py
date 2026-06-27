from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.server.database import list_templates, get_template, save_template

router = APIRouter(prefix="/api/templates", tags=["templates"])

# Pre-built templates from disk (absolute path, independent of cwd)
_BUILTIN_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


@router.get("")
async def api_list_templates():
    results = {}

    # Load built-in templates
    if _BUILTIN_DIR.exists():
        for f in sorted(_BUILTIN_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                results[f.stem] = {
                    "id": f.stem,
                    "name": data.get("metadata", {}).get("name", f.stem),
                    "builtin": True,
                    "graph_json": f.read_text(),
                }
            except Exception:
                continue

    # Load user templates from DB
    for t in await list_templates():
        results[t["id"]] = {
            "id": t["id"],
            "name": t["name"],
            "builtin": False,
            "graph_json": None,  # full graph not in list
            "created_at": t["created_at"],
        }

    return list(results.values())


@router.get("/{template_id}")
async def api_get_template(template_id: str):
    # Check built-in first
    builtin_path = _BUILTIN_DIR / f"{template_id}.json"
    if builtin_path.exists():
        data = json.loads(builtin_path.read_text())
        return {
            "id": template_id,
            "name": data.get("metadata", {}).get("name", template_id),
            "builtin": True,
            "graph_json": builtin_path.read_text(),
        }

    # Check DB
    t = await get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="template not found")
    return {"id": t["id"], "name": t["name"], "builtin": False, "graph_json": t["graph_json"]}


@router.post("")
async def api_save_template(body: dict):
    name = body.get("name", "").strip()
    graph_json = body.get("graph_json", "")
    if not name or not graph_json:
        raise HTTPException(status_code=400, detail="name and graph_json are required")
    t = await save_template(name, graph_json)
    return {"id": t["id"], "name": t["name"]}
