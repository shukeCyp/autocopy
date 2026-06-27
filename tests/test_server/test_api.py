import json

import pytest
from httpx import AsyncClient, ASGITransport


# Ensure nodes are registered before importing server
import app.nodes  # noqa: F401
from app.server.main import app as fastapi_app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Create an async test client with isolated DB."""
    monkeypatch.chdir(tmp_path)
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_templates_returns_builtins(client):
    r = await client.get("/api/templates")
    assert r.status_code == 200
    templates = r.json()
    names = [t["id"] for t in templates]
    assert "quick_chinese" in names
    assert "quick_english" in names
    assert "tts_only" in names


@pytest.mark.asyncio
async def test_get_builtin_template(client):
    r = await client.get("/api/templates/quick_chinese")
    assert r.status_code == 200
    data = r.json()
    assert "graph_json" in data
    graph = json.loads(data["graph_json"])
    assert len(graph["nodes"]) == 8


@pytest.mark.asyncio
async def test_settings_roundtrip(client):
    r = await client.put("/api/settings", json={"api_key": "test-key"})
    assert r.status_code == 200

    r = await client.get("/api/settings")
    assert r.json() == {"api_key": "test-key"}


@pytest.mark.asyncio
async def test_save_and_list_user_template(client):
    r = await client.post("/api/templates", json={
        "name": "My Custom",
        "graph_json": '{"nodes":[],"edges":[]}',
    })
    assert r.status_code == 200
    template_id = r.json()["id"]

    r = await client.get(f"/api/templates/{template_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "My Custom"


@pytest.mark.asyncio
async def test_list_tasks_empty(client):
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_graph_run_creates_task(client, monkeypatch):
    import app.nodes  # noqa
    from app.server.routes import graph as graph_module

    # Replace actual execution with no-op
    original = graph_module._run_graph

    async def fake_run(task_id, graph_json):
        from app.server.database import update_task
        await update_task(task_id, status="done", current_step="完成")

    monkeypatch.setattr(graph_module, "_run_graph", fake_run)

    graph_json = json.dumps({
        "nodes": [{
            "id": "n1", "type": "VideoInput", "label": "test",
            "x": 0, "y": 0, "status": "idle",
            "inputs": {}, "outputs": {"video_info": {"name": "video_info", "port_type": "video_info"}},
            "params": {"path": {"name": "path", "param_type": "string", "default": ""}},
        }],
        "edges": [],
    })

    r = await client.post("/api/graph/run", json={
        "graph_json": graph_json,
        "task_name": "test task",
    })
    assert r.status_code == 200
    task_id = r.json()["task_id"]

    # Wait for background task
    import asyncio
    await asyncio.sleep(0.2)

    r = await client.get(f"/api/tasks/{task_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "done"


@pytest.mark.asyncio
async def test_delete_task(client):
    from app.server.database import create_task
    task = await create_task("delete-me", "{}")
    r = await client.delete(f"/api/tasks/{task['id']}")
    assert r.status_code == 200
    r = await client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 404
