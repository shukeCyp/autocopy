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
async def test_select_directory_returns_chosen_path(client, tmp_path, monkeypatch):
    from app.server.routes import files as files_module

    chosen = tmp_path / "drafts"
    chosen.mkdir()
    monkeypatch.setattr(files_module, "select_directory", lambda: chosen)

    r = await client.post("/api/files/select-directory")

    assert r.status_code == 200
    assert r.json() == {"path": str(chosen.resolve())}


@pytest.mark.asyncio
async def test_select_directory_returns_empty_path_when_cancelled(client, monkeypatch):
    from app.server.routes import files as files_module

    monkeypatch.setattr(files_module, "select_directory", lambda: None)

    r = await client.post("/api/files/select-directory")

    assert r.status_code == 200
    assert r.json() == {"path": ""}


@pytest.mark.asyncio
async def test_list_templates_returns_workflows_without_builtin_flag(client):
    r = await client.get("/api/templates")
    assert r.status_code == 200
    templates = r.json()
    names = [t["id"] for t in templates]
    assert "quick_chinese" in names
    assert "quick_english" in names
    assert "tts_only" in names
    assert "tts_script_strip" in names
    assert all("builtin" not in template for template in templates)


@pytest.mark.asyncio
async def test_workflow_template_files_are_pluggable(client, tmp_path, monkeypatch):
    template_dir = tmp_path / "workflow_templates"
    template_dir.mkdir()
    graph = {
        "template_id": "plugged_flow",
        "metadata": {"name": "Plugged Flow", "description": "Loaded from configured directory"},
        "nodes": [],
        "edges": [],
    }
    (template_dir / "plugged-flow.json").write_text(json.dumps(graph), encoding="utf-8")
    monkeypatch.setenv("WORKFLOW_TEMPLATE_DIRS", str(template_dir))

    r = await client.get("/api/templates")
    assert r.status_code == 200
    plugged = next(template for template in r.json() if template["id"] == "plugged_flow")
    assert plugged["name"] == "Plugged Flow"
    assert plugged["description"] == "Loaded from configured directory"
    assert "builtin" not in plugged

    r = await client.get("/api/templates/plugged_flow")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "plugged_flow"
    assert data["name"] == "Plugged Flow"
    assert json.loads(data["graph_json"]) == graph
    assert "builtin" not in data


@pytest.mark.asyncio
async def test_get_default_workflow_template(client):
    r = await client.get("/api/templates/quick_chinese")
    assert r.status_code == 200
    data = r.json()
    assert "graph_json" in data
    assert "builtin" not in data
    graph = json.loads(data["graph_json"])
    node_types = [node["type"] for node in graph["nodes"]]
    assert node_types == [
        "VideoInput",
        "VideoInput",
        "VideoAudioExtract",
        "VocalSeparation",
        "VoiceVAD",
        "DominantSpeaker",
        "SegmentASR",
        "SRTRewrite",
        "VideoMatch",
        "TTSGenerate",
        "JianyingMerge",
    ]
    assert "TTSExtract" not in node_types
    segment_asr = next(node for node in graph["nodes"] if node["id"] == "segment_asr")
    assert segment_asr["outputs"]["srt_content"]["port_type"] == "srt_content"
    video_match = next(node for node in graph["nodes"] if node["id"] == "video_match")
    assert set(video_match["outputs"]) == {"segments_json"}
    jianying_merge = next(node for node in graph["nodes"] if node["id"] == "jianying_merge")
    assert jianying_merge["type"] == "JianyingMerge"
    assert set(jianying_merge["inputs"]) == {"segments_json", "rewritten_srt"}
    assert {
        "source_node_id": "segment_asr",
        "source_port": "srt_content",
        "target_node_id": "srt_rewrite",
        "target_port": "srt_content",
    } in graph["edges"]
    assert {
        "source_node_id": "video_match",
        "source_port": "segments_json",
        "target_node_id": "jianying_merge",
        "target_port": "segments_json",
    } in graph["edges"]
    assert {
        "source_node_id": "srt_rewrite",
        "source_port": "rewritten_srt",
        "target_node_id": "jianying_merge",
        "target_port": "rewritten_srt",
    } in graph["edges"]


@pytest.mark.asyncio
async def test_get_tts_script_strip_template(client):
    r = await client.get("/api/templates/tts_script_strip")
    assert r.status_code == 200
    data = r.json()
    graph = json.loads(data["graph_json"])

    assert data["name"] == "TTS文案剥离"
    assert [node["type"] for node in graph["nodes"]] == [
        "VideoInput",
        "VideoAudioExtract",
        "VocalSeparation",
        "VoiceVAD",
        "DominantSpeaker",
        "SegmentASR",
    ]
    assert graph["edges"][0] == {
        "source_node_id": "input_video",
        "source_port": "video_info",
        "target_node_id": "audio_extract",
        "target_port": "video_info",
    }
    assert graph["edges"][1] == {
        "source_node_id": "audio_extract",
        "source_port": "audio_path",
        "target_node_id": "vocal_separation",
        "target_port": "audio_path",
    }
    assert graph["edges"][-1] == {
        "source_node_id": "dominant_speaker",
        "source_port": "dominant_segments_json",
        "target_node_id": "segment_asr",
        "target_port": "segments_json",
    }
    segment_asr = next(node for node in graph["nodes"] if node["id"] == "segment_asr")
    assert segment_asr["params"]["timing_offset_ms"]["default"] == 820
    assert segment_asr["outputs"]["srt_content"]["port_type"] == "srt_content"


@pytest.mark.asyncio
async def test_list_node_schemas(client):
    r = await client.get("/api/nodes")
    assert r.status_code == 200
    schemas = r.json()

    by_type = {schema["type"]: schema for schema in schemas}
    assert "SegmentASR" in by_type
    assert "VideoMatchVMF" in by_type
    assert "JianyingMerge" in by_type
    assert "TTSExtract" not in by_type
    assert by_type["SegmentASR"]["params"]["timing_offset_ms"]["param_type"] == "int"
    assert by_type["SegmentASR"]["outputs"]["srt_content"]["port_type"] == "srt_content"
    assert set(by_type["VideoMatch"]["outputs"]) == {"segments_json"}
    assert set(by_type["VideoMatchVMF"]["outputs"]) == {"segments_json", "vmf_results_json"}
    assert by_type["VideoMatchVMF"]["outputs"]["vmf_results_json"]["port_type"] == "file_path"
    assert set(by_type["JianyingMerge"]["inputs"]) == {"segments_json", "rewritten_srt"}
    assert set(by_type["JianyingMerge"]["outputs"]) == {"draft_path"}
    assert by_type["VideoInput"]["params"]["path"]["required"] is True


@pytest.mark.asyncio
async def test_get_single_node_schema(client):
    r = await client.get("/api/nodes/VoiceVAD")
    assert r.status_code == 200
    schema = r.json()

    assert schema["type"] == "VoiceVAD"
    assert schema["params"]["vad_model"]["required"] is True


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
        "description": "My workflow description",
        "graph_json": '{"nodes":[],"edges":[]}',
    })
    assert r.status_code == 200
    template_id = r.json()["id"]

    r = await client.get(f"/api/templates/{template_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "My Custom"
    assert r.json()["description"] == "My workflow description"

    r = await client.get("/api/templates")
    listed = next(t for t in r.json() if t["id"] == template_id)
    assert listed["description"] == "My workflow description"

    r = await client.put(f"/api/templates/{template_id}", json={
        "name": "My Custom",
        "description": "Updated description",
        "graph_json": '{"nodes":[],"edges":[]}',
    })
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_user_template(client):
    r = await client.post("/api/templates", json={
        "name": "Delete Me",
        "graph_json": '{"nodes":[],"edges":[]}',
    })
    assert r.status_code == 200
    template_id = r.json()["id"]

    r = await client.delete(f"/api/templates/{template_id}")
    assert r.status_code == 200

    r = await client.get(f"/api/templates/{template_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_default_template_can_be_updated_and_reset(client):
    r = await client.get("/api/templates/quick_chinese")
    original = r.json()
    graph_json = original["graph_json"]

    r = await client.put("/api/templates/quick_chinese", json={
        "name": "我的固定流程",
        "description": "updated",
        "graph_json": graph_json,
    })
    assert r.status_code == 200
    assert r.json()["name"] == "我的固定流程"

    r = await client.get("/api/templates/quick_chinese")
    assert r.json()["name"] == "我的固定流程"
    assert "builtin" not in r.json()

    r = await client.delete("/api/templates/quick_chinese")
    assert r.status_code == 200

    r = await client.get("/api/templates/quick_chinese")
    assert r.json()["name"] == original["name"]


@pytest.mark.asyncio
async def test_saved_workflow_graphs_are_upgraded_to_srt_content(client):
    old_graph = {
        "nodes": [
            {
                "id": "segment_asr",
                "type": "SegmentASR",
                "label": "ASR 输出 SRT",
                "x": 0,
                "y": 0,
                "status": "idle",
                "inputs": {"segments_json": {"name": "segments_json", "port_type": "file_path"}},
                "outputs": {"srt_path": {"name": "srt_path", "port_type": "file_path"}},
                "params": {},
            },
            {
                "id": "srt_rewrite",
                "type": "SRTRewrite",
                "label": "文案改写",
                "x": 400,
                "y": 0,
                "status": "idle",
                "inputs": {"srt_path": {"name": "srt_path", "port_type": "file_path"}},
                "outputs": {"rewritten_srt": {"name": "rewritten_srt", "port_type": "file_path"}},
                "params": {},
            },
        ],
        "edges": [
            {
                "source_node_id": "segment_asr",
                "source_port": "srt_path",
                "target_node_id": "srt_rewrite",
                "target_port": "srt_path",
            }
        ],
    }

    r = await client.put("/api/templates/tts_only", json={
        "name": "旧端口保存流程",
        "description": "",
        "graph_json": json.dumps(old_graph),
    })
    assert r.status_code == 200

    r = await client.get("/api/templates/tts_only")
    graph = json.loads(r.json()["graph_json"])

    segment_asr = next(node for node in graph["nodes"] if node["id"] == "segment_asr")
    srt_rewrite = next(node for node in graph["nodes"] if node["id"] == "srt_rewrite")
    assert segment_asr["outputs"]["srt_content"]["port_type"] == "srt_content"
    assert "srt_path" not in segment_asr["outputs"]
    assert srt_rewrite["inputs"]["srt_content"]["port_type"] == "srt_content"
    assert "srt_path" not in srt_rewrite["inputs"]
    assert graph["edges"] == [
        {
            "source_node_id": "segment_asr",
            "source_port": "srt_content",
            "target_node_id": "srt_rewrite",
            "target_port": "srt_content",
        }
    ]


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
async def test_run_graph_marks_unsuccessful_result_failed(client, monkeypatch):
    from app.pipeline.types import NodeResult, NodeStatus
    from app.server.database import create_task, get_task
    from app.server.routes import graph as graph_module

    class FakeResult:
        success = False
        node_results = [
            NodeResult(
                node_id="n1",
                status=NodeStatus.FAILED,
                outputs={},
                error="bad input",
            )
        ]

        def to_dict(self):
            return {
                "success": self.success,
                "node_results": [r.to_dict() for r in self.node_results],
                "outputs": {},
                "total_duration_ms": 0.0,
            }

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, graph):
            return FakeResult()

    monkeypatch.setattr(graph_module, "Executor", FakeExecutor)

    graph_json = json.dumps({
        "nodes": [{
            "id": "n1", "type": "VideoInput", "label": "test",
            "x": 0, "y": 0, "status": "idle",
            "inputs": {},
            "outputs": {"video_info": {"name": "video_info", "port_type": "video_info"}},
            "params": {"path": {"name": "path", "param_type": "string", "default": ""}},
        }],
        "edges": [],
    })
    task = await create_task("failed task", graph_json)

    await graph_module._run_graph(task["id"], graph_json)

    updated = await get_task(task["id"])
    assert updated["status"] == "failed"
    assert updated["current_step"] == "失败"
    assert updated["error"] == "bad input"
    assert json.loads(updated["result_json"])["success"] is False


@pytest.mark.asyncio
async def test_run_graph_broadcasts_executing_and_validation_issues(client, monkeypatch):
    from app.server.database import create_task
    from app.server.routes import graph as graph_module

    graph_json = json.dumps({
        "nodes": [{
            "id": "input_video", "type": "VideoInput", "label": "test",
            "x": 0, "y": 0, "status": "idle",
            "inputs": {},
            "outputs": {"video_info": {"name": "video_info", "port_type": "video_info"}},
            "params": {"path": {"name": "path", "param_type": "string", "default": ""}},
        }],
        "edges": [],
    })
    task = await create_task("validation broadcast", graph_json)
    events = []

    async def collect(task_id, data):
        events.append(data)

    monkeypatch.setattr(graph_module.manager, "broadcast", collect)

    await graph_module._run_graph(task["id"], graph_json)

    assert any(
        event["type"] == "node_executing" and event["node_id"] == "input_video"
        for event in events
    )
    error_event = next(event for event in events if event["type"] == "node_error")
    assert error_event["data"]["validation_issues"][0]["code"] == "missing_param"


@pytest.mark.asyncio
async def test_run_graph_persists_current_node_for_polling(client):
    from app.server.database import create_task, get_task
    from app.server.routes import graph as graph_module

    graph_json = json.dumps({
        "nodes": [{
            "id": "input_video", "type": "VideoInput", "label": "加载视频",
            "x": 0, "y": 0, "status": "idle",
            "inputs": {},
            "outputs": {"video_info": {"name": "video_info", "port_type": "video_info"}},
            "params": {"path": {"name": "path", "param_type": "string", "default": ""}},
        }],
        "edges": [],
    })
    task = await create_task("current node polling", graph_json)

    await graph_module._run_graph(task["id"], graph_json)

    updated = await get_task(task["id"])
    assert updated["status"] == "failed"
    assert updated["current_node_id"] == "input_video"
    assert updated["current_node_label"] == "加载视频"


@pytest.mark.asyncio
async def test_delete_task(client):
    from app.server.database import create_task
    task = await create_task("delete-me", "{}")
    r = await client.delete(f"/api/tasks/{task['id']}")
    assert r.status_code == 200
    r = await client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 404
