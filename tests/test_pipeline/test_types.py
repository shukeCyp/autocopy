import json

from app.pipeline.types import (
    NodeStatus,
    ParamSpec,
    PortSpec,
    PortType,
    NodeResult,
    ExecutorEvent,
)


class TestPortType:
    def test_port_type_values(self):
        assert PortType.FILE_PATH.value == "file_path"
        assert PortType.SRT_CONTENT.value == "srt_content"
        assert PortType.VIDEO_INFO.value == "video_info"
        assert PortType.AUDIO_SEGMENTS.value == "audio_segments"
        assert PortType.JSON_DATA.value == "json_data"

    def test_port_type_is_json_serializable(self):
        data = {"type": PortType.FILE_PATH.value}
        assert json.dumps(data) == '{"type": "file_path"}'


class TestPortSpec:
    def test_create_required_port(self):
        spec = PortSpec(name="video", port_type=PortType.FILE_PATH, required=True)
        assert spec.name == "video"
        assert spec.port_type == PortType.FILE_PATH
        assert spec.required is True
        assert spec.description == ""

    def test_create_optional_port_with_description(self):
        spec = PortSpec(
            name="subtitles",
            port_type=PortType.SRT_CONTENT,
            required=False,
            description="Optional subtitle track",
        )
        assert spec.name == "subtitles"
        assert spec.required is False
        assert spec.description == "Optional subtitle track"

    def test_default_required_is_true(self):
        spec = PortSpec(name="input", port_type=PortType.FILE_PATH)
        assert spec.required is True

    def test_ports_are_hashable(self):
        spec = PortSpec(name="video", port_type=PortType.FILE_PATH)
        d = {spec: "value"}
        assert d[spec] == "value"

    def test_to_dict(self):
        spec = PortSpec(name="video", port_type=PortType.FILE_PATH, description="Source video")
        d = spec.to_dict()
        assert d == {"name": "video", "port_type": "file_path", "required": True, "description": "Source video"}

    def test_from_dict(self):
        d = {"name": "audio", "port_type": "audio_segments", "required": False, "description": "TTS audio"}
        spec = PortSpec.from_dict(d)
        assert spec.name == "audio"
        assert spec.port_type == PortType.AUDIO_SEGMENTS
        assert spec.required is False
        assert spec.description == "TTS audio"

    def test_from_dict_defaults(self):
        spec = PortSpec.from_dict({"name": "data", "port_type": "json_data"})
        assert spec.required is True
        assert spec.description == ""


class TestParamSpec:
    def test_create_param(self):
        spec = ParamSpec(
            name="language",
            param_type="string",
            default="Chinese",
            description="Target language for rewrite",
        )
        assert spec.name == "language"
        assert spec.param_type == "string"
        assert spec.default == "Chinese"
        assert spec.description == "Target language for rewrite"

    def test_to_dict(self):
        spec = ParamSpec(name="threshold", param_type="float", default=0.5)
        d = spec.to_dict()
        assert d == {
            "name": "threshold",
            "param_type": "float",
            "default": 0.5,
            "description": "",
            "required": False,
        }

    def test_from_dict(self):
        d = {"name": "speed", "param_type": "float", "default": 1.0, "description": "Voice speed"}
        spec = ParamSpec.from_dict(d)
        assert spec.name == "speed"
        assert spec.param_type == "float"
        assert spec.default == 1.0
        assert spec.description == "Voice speed"


class TestNodeStatus:
    def test_status_values(self):
        assert NodeStatus.IDLE.value == "idle"
        assert NodeStatus.QUEUED.value == "queued"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.DONE.value == "done"
        assert NodeStatus.FAILED.value == "failed"
        assert NodeStatus.SKIPPED.value == "skipped"


class TestNodeResult:
    def test_create_success_result(self):
        result = NodeResult(
            node_id="n1",
            status=NodeStatus.DONE,
            outputs={"final_srt": "/tmp/out.srt"},
        )
        assert result.success is True
        assert result.outputs["final_srt"] == "/tmp/out.srt"
        assert result.error is None

    def test_create_failed_result(self):
        result = NodeResult(
            node_id="n2",
            status=NodeStatus.FAILED,
            outputs={},
            error="Minimax API timeout",
        )
        assert result.success is False
        assert result.error == "Minimax API timeout"

    def test_to_dict(self):
        result = NodeResult(
            node_id="n1",
            status=NodeStatus.DONE,
            outputs={"srt": "/tmp/out.srt"},
            duration_ms=1234,
        )
        d = result.to_dict()
        assert d == {
            "node_id": "n1",
            "status": "done",
            "outputs": {"srt": "/tmp/out.srt"},
            "error": None,
            "duration_ms": 1234,
            "validation_issues": [],
        }


class TestExecutorEvent:
    def test_node_status_event(self):
        event = ExecutorEvent.node_status("n1", NodeStatus.RUNNING, progress=0.5)
        assert event.event_type == "node_status"
        assert event.node_id == "n1"
        assert event.data["status"] == "running"
        assert event.data["progress"] == 0.5

    def test_node_done_event(self):
        event = ExecutorEvent.node_done("n1", {"srt": "/tmp/out.srt"})
        assert event.event_type == "node_done"
        assert event.data["outputs"] == {"srt": "/tmp/out.srt"}

    def test_node_error_event(self):
        event = ExecutorEvent.node_error("n1", "something broke")
        assert event.event_type == "node_error"
        assert event.data["error"] == "something broke"

    def test_graph_complete_event(self):
        event = ExecutorEvent.graph_complete("task-1", {"final": "/tmp/final.mp4"})
        assert event.event_type == "graph_complete"
        assert event.data["task_id"] == "task-1"
        assert event.data["outputs"] == {"final": "/tmp/final.mp4"}

    def test_log_event(self):
        event = ExecutorEvent.log("n1", "info", "processing chunk 3/10")
        assert event.event_type == "log"
        assert event.data["level"] == "info"
        assert event.data["message"] == "processing chunk 3/10"
