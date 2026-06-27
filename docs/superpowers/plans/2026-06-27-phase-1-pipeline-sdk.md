# Phase 1 — Pipeline SDK 核心 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建纯 Python Pipeline SDK 核心——Node 基类、Edge、Graph（拓扑排序+序列化）、Executor（缓存+调度）。完全独立于 UI，可独立测试。

**Architecture:** 四个核心模块 (`types.py` → `node.py` → `edge.py` → `graph.py` → `executor.py`)，每个依赖前一个。Graph 是节点+连线的集合，支持 JSON 序列化。Executor 接收 Graph，拓扑排序后逐个执行 Node，基于内容哈希做产物缓存。

**Tech Stack:** Python 3.10+, dataclasses, enum, asyncio, hashlib, json, pathlib. 零外部依赖。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `app/pipeline/__init__.py` | 导出所有公开符号 |
| `app/pipeline/types.py` | PortType, PortSpec, ParamSpec, NodeStatus, NodeResult, ExecutorEvent |
| `app/pipeline/node.py` | Node 基类——状态机, run(), cache_key() |
| `app/pipeline/edge.py` | Edge——连接两个节点的端口，类型兼容性校验 |
| `app/pipeline/graph.py` | Graph——节点+连线集合，拓扑排序，环检测，JSON 序列化 |
| `app/pipeline/executor.py` | Executor——接收 Graph，按序执行，缓存管理，进度回调 |
| `tests/test_pipeline/__init__.py` | 空文件 |
| `tests/test_pipeline/test_types.py` | 类型定义测试 |
| `tests/test_pipeline/test_node.py` | Node 基类测试 |
| `tests/test_pipeline/test_edge.py` | Edge 测试 |
| `tests/test_pipeline/test_graph.py` | Graph 拓扑排序+序列化测试 |
| `tests/test_pipeline/test_executor.py` | Executor 缓存+调度测试 |

---

### Task 1: 端口类型系统 (`types.py`)

**Files:**
- Create: `app/pipeline/__init__.py`
- Create: `app/pipeline/types.py`
- Create: `tests/test_pipeline/__init__.py`
- Create: `tests/test_pipeline/test_types.py`

- [ ] **Step 1: 创建测试目录和空 __init__.py**

```bash
mkdir -p app/pipeline tests/test_pipeline
touch app/pipeline/__init__.py tests/test_pipeline/__init__.py
```

- [ ] **Step 2: 写 types.py 测试**

在 `tests/test_pipeline/test_types.py`:

```python
import json
from enum import Enum

import pytest

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
        assert d == {"name": "threshold", "param_type": "float", "default": 0.5, "description": ""}

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
```

- [ ] **Step 3: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_pipeline/test_types.py -v
```
Expected: all FAIL with ModuleNotFoundError

- [ ] **Step 4: 实现 `app/pipeline/types.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PortType(Enum):
    FILE_PATH = "file_path"
    SRT_CONTENT = "srt_content"
    VIDEO_INFO = "video_info"
    AUDIO_SEGMENTS = "audio_segments"
    JSON_DATA = "json_data"


@dataclass(frozen=True)
class PortSpec:
    name: str
    port_type: PortType
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "port_type": self.port_type.value,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PortSpec:
        return cls(
            name=d["name"],
            port_type=PortType(d["port_type"]),
            required=d.get("required", True),
            description=d.get("description", ""),
        )


@dataclass(frozen=True)
class ParamSpec:
    name: str
    param_type: str  # "string", "float", "int", "bool", "select"
    default: Any = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "param_type": self.param_type,
            "default": self.default,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ParamSpec:
        return cls(
            name=d["name"],
            param_type=d["param_type"],
            default=d.get("default"),
            description=d.get("description", ""),
        )


class NodeStatus(Enum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeResult:
    node_id: str
    status: NodeStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == NodeStatus.DONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "outputs": self.outputs,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ExecutorEvent:
    event_type: str
    node_id: str | None
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def node_status(cls, node_id: str, status: NodeStatus, progress: float = 0.0) -> ExecutorEvent:
        return cls(
            event_type="node_status",
            node_id=node_id,
            data={"status": status.value, "progress": progress},
        )

    @classmethod
    def node_done(cls, node_id: str, outputs: dict[str, Any]) -> ExecutorEvent:
        return cls(
            event_type="node_done",
            node_id=node_id,
            data={"outputs": outputs},
        )

    @classmethod
    def node_error(cls, node_id: str, error: str) -> ExecutorEvent:
        return cls(
            event_type="node_error",
            node_id=node_id,
            data={"error": error},
        )

    @classmethod
    def graph_complete(cls, task_id: str, outputs: dict[str, Any]) -> ExecutorEvent:
        return cls(
            event_type="graph_complete",
            node_id=None,
            data={"task_id": task_id, "outputs": outputs},
        )

    @classmethod
    def log(cls, node_id: str | None, level: str, message: str) -> ExecutorEvent:
        return cls(
            event_type="log",
            node_id=node_id,
            data={"level": level, "message": message},
        )
```

- [ ] **Step 5: 实现 `app/pipeline/__init__.py`**

```python
from app.pipeline.types import (
    ExecutorEvent,
    NodeResult,
    NodeStatus,
    ParamSpec,
    PortSpec,
    PortType,
)
from app.pipeline.node import Node
from app.pipeline.edge import Edge
from app.pipeline.graph import Graph
from app.pipeline.executor import Executor

__all__ = [
    "Node",
    "Edge",
    "Graph",
    "Executor",
    "PortType",
    "PortSpec",
    "ParamSpec",
    "NodeStatus",
    "NodeResult",
    "ExecutorEvent",
]
```

- [ ] **Step 6: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_pipeline/test_types.py -v
```
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add app/pipeline/ tests/test_pipeline/
git commit -m "feat: add pipeline types - PortSpec, ParamSpec, NodeStatus, NodeResult, ExecutorEvent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Node 基类 (`node.py`)

**Files:**
- Create: `app/pipeline/node.py`
- Create: `tests/test_pipeline/test_node.py`

- [ ] **Step 1: 写 Node 基类测试**

在 `tests/test_pipeline/test_node.py`:

```python
from pathlib import Path

import pytest

from app.pipeline.types import NodeStatus, PortSpec, PortType, ParamSpec, NodeResult
from app.pipeline.node import Node


class AddNode(Node):
    """Test node that adds two numbers."""
    node_type = "Add"

    def _define(self):
        self.inputs = {
            "a": PortSpec(name="a", port_type=PortType.JSON_DATA),
            "b": PortSpec(name="b", port_type=PortType.JSON_DATA),
        }
        self.outputs = {
            "sum": PortSpec(name="sum", port_type=PortType.JSON_DATA),
        }
        self.params = {
            "offset": ParamSpec(name="offset", param_type="int", default=0),
        }

    async def run(self, inputs, params, work_dir):
        a = inputs["a"]
        b = inputs["b"]
        offset = params.get("offset", 0)
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"sum": a + b + offset},
        )


class IdentityNode(Node):
    """Test node that passes input straight through."""
    node_type = "Identity"

    def _define(self):
        self.inputs = {
            "value": PortSpec(name="value", port_type=PortType.JSON_DATA),
        }
        self.outputs = {
            "value": PortSpec(name="value", port_type=PortType.JSON_DATA),
        }
        self.params = {}

    async def run(self, inputs, params, work_dir):
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"value": inputs["value"]},
        )


class FailingNode(Node):
    """Test node that always fails."""
    node_type = "Failing"

    def _define(self):
        self.inputs = {}
        self.outputs = {
            "result": PortSpec(name="result", port_type=PortType.JSON_DATA),
        }
        self.params = {}

    async def run(self, inputs, params, work_dir):
        raise RuntimeError("intentional failure")


class TestNode:
    def test_node_has_unique_id(self):
        a = AddNode(label="adder")
        b = AddNode(label="adder")
        assert a.id != b.id
        assert len(a.id) > 0

    def test_node_type_is_class_attribute(self):
        node = AddNode(label="test")
        assert node.type == "Add"

    def test_node_label(self):
        node = AddNode(label="My Adder")
        assert node.label == "My Adder"

    def test_default_label_is_node_type(self):
        node = IdentityNode()
        assert node.label == "Identity"

    def test_initial_status_is_idle(self):
        node = AddNode()
        assert node.status == NodeStatus.IDLE

    def test_node_has_inputs(self):
        node = AddNode()
        assert "a" in node.inputs
        assert "b" in node.inputs
        assert node.inputs["a"].port_type == PortType.JSON_DATA

    def test_node_has_outputs(self):
        node = AddNode()
        assert "sum" in node.outputs
        assert node.outputs["sum"].port_type == PortType.JSON_DATA

    def test_node_has_params(self):
        node = AddNode()
        assert "offset" in node.params
        assert node.params["offset"].default == 0

    def test_node_position(self):
        node = AddNode(x=100, y=200)
        assert node.x == 100
        assert node.y == 200

    def test_default_position_is_zero(self):
        node = AddNode()
        assert node.x == 0
        assert node.y == 0

    @pytest.mark.asyncio
    async def test_run_returns_node_result(self, tmp_path):
        node = AddNode()
        result = await node.run({"a": 3, "b": 4}, {"offset": 1}, tmp_path)
        assert result.success is True
        assert result.outputs["sum"] == 8

    @pytest.mark.asyncio
    async def test_run_updates_status(self, tmp_path):
        node = AddNode()
        await node.execute({"a": 1, "b": 2}, {}, tmp_path)
        assert node.status == NodeStatus.DONE

    @pytest.mark.asyncio
    async def test_execute_sets_status_running_then_done(self, tmp_path):
        node = AddNode()
        statuses = []

        original_run = node.run

        async def tracking_run(inputs, params, work_dir):
            statuses.append(node.status)
            result = await original_run(inputs, params, work_dir)
            statuses.append(node.status)
            return result

        node.run = tracking_run
        await node.execute({"a": 1, "b": 1}, {}, tmp_path)
        assert statuses[0] == NodeStatus.RUNNING
        assert statuses[1] == NodeStatus.DONE

    @pytest.mark.asyncio
    async def test_execute_on_failure_sets_status_failed(self, tmp_path):
        node = FailingNode()
        try:
            await node.execute({}, {}, tmp_path)
        except RuntimeError:
            pass
        assert node.status == NodeStatus.FAILED

    def test_cache_key_is_stable(self):
        node = AddNode()
        key1 = node.cache_key({"a": 10, "b": 20}, {"offset": 0})
        key2 = node.cache_key({"a": 10, "b": 20}, {"offset": 0})
        assert key1 == key2

    def test_cache_key_changes_with_different_inputs(self):
        node = AddNode()
        key1 = node.cache_key({"a": 1, "b": 2}, {})
        key2 = node.cache_key({"a": 3, "b": 4}, {})
        assert key1 != key2

    def test_cache_key_changes_with_different_params(self):
        node = AddNode()
        key1 = node.cache_key({"a": 1, "b": 2}, {"offset": 0})
        key2 = node.cache_key({"a": 1, "b": 2}, {"offset": 10})
        assert key1 != key2

    def test_cache_key_includes_node_type(self):
        add = AddNode()
        identity = IdentityNode()
        key1 = add.cache_key({"a": 1, "b": 2}, {})
        key2 = identity.cache_key({"value": {"a": 1, "b": 2}}, {})
        assert key1 != key2

    def test_to_dict(self):
        node = AddNode(label="adder", x=100, y=200)
        d = node.to_dict()
        assert d["id"] == node.id
        assert d["type"] == "Add"
        assert d["label"] == "adder"
        assert d["x"] == 100
        assert d["y"] == 200
        assert d["status"] == "idle"
        assert "a" in d["inputs"]
        assert "b" in d["inputs"]
        assert "sum" in d["outputs"]
        assert "offset" in d["params"]
        assert d["params"]["offset"]["default"] == 0

    def test_from_dict(self):
        d = {
            "id": "n1",
            "type": "Add",
            "label": "adder",
            "x": 42,
            "y": 99,
            "status": "done",
            "inputs": {
                "a": {"name": "a", "port_type": "json_data"},
                "b": {"name": "b", "port_type": "json_data"},
            },
            "outputs": {
                "sum": {"name": "sum", "port_type": "json_data"},
            },
            "params": {
                "offset": {"name": "offset", "param_type": "int", "default": 0},
            },
        }
        node = Node.from_dict(d)
        assert node.id == "n1"
        assert node.type == "Add"
        assert node.label == "adder"
        assert node.x == 42
        assert node.y == 99
        assert node.status == NodeStatus.DONE
        assert node.inputs["a"].port_type == PortType.JSON_DATA
        assert node.outputs["sum"].port_type == PortType.JSON_DATA
        assert node.params["offset"].default == 0
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_pipeline/test_node.py -v
```
Expected: all FAIL

- [ ] **Step 3: 实现 `app/pipeline/node.py`**

```python
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec


class Node(ABC):
    """Base class for all pipeline nodes.

    Subclasses define their interface by implementing _define() and run().
    The constructor calls _define() to populate inputs, outputs, and params.
    """

    node_type: str = ""

    def __init__(
        self,
        id: str | None = None,
        label: str = "",
        x: float = 0,
        y: float = 0,
    ):
        self.id = id or uuid4().hex[:12]
        self.label = label or self.node_type
        self.x = x
        self.y = y
        self.status: NodeStatus = NodeStatus.IDLE
        self.inputs: dict[str, PortSpec] = {}
        self.outputs: dict[str, PortSpec] = {}
        self.params: dict[str, ParamSpec] = {}
        self._define()

    @property
    def type(self) -> str:
        return self.node_type

    @abstractmethod
    def _define(self) -> None:
        """Subclasses override this to set self.inputs, self.outputs, self.params."""
        ...

    @abstractmethod
    async def run(self, inputs: dict[str, Any], params: dict[str, Any], work_dir: Path) -> NodeResult:
        """Execute the node's logic. inputs are the resolved upstream output values.
        params are the current param values (merged with defaults from self.params).
        """
        ...

    async def execute(
        self,
        inputs: dict[str, Any],
        params: dict[str, Any],
        work_dir: Path,
    ) -> NodeResult:
        """Wrapper around run() that manages status transitions and timing."""
        self.status = NodeStatus.RUNNING
        start = time.monotonic()
        try:
            result = await self.run(inputs, params, work_dir)
            self.status = NodeStatus.DONE
            result.duration_ms = (time.monotonic() - start) * 1000
            return result
        except Exception:
            self.status = NodeStatus.FAILED
            raise

    def cache_key(self, inputs: dict[str, Any], params: dict[str, Any]) -> str:
        """Stable cache key based on node type, inputs, and params.
        Uses SHA256 for collision resistance.
        """
        payload = {
            "node_type": self.node_type,
            "inputs": inputs,
            "params": params,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.node_type,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "status": self.status.value,
            "inputs": {name: spec.to_dict() for name, spec in self.inputs.items()},
            "outputs": {name: spec.to_dict() for name, spec in self.outputs.items()},
            "params": {name: spec.to_dict() for name, spec in self.params.items()},
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Node:
        """Reconstruct a Node from its dict representation.
        Note: This reconstructs the interface (ports/params) but does NOT
        restore a concrete subclass. Callers should use a registry to
        look up the correct class by d['type'].
        """
        class_name = d["type"]
        node_cls = _NODE_REGISTRY.get(class_name)
        if node_cls is None:
            raise ValueError(
                f"Unknown node type '{class_name}'. "
                f"Register it with Node.register() or use a known type."
            )
        node = node_cls(
            id=d["id"],
            label=d.get("label", class_name),
            x=d.get("x", 0),
            y=d.get("y", 0),
        )
        node.status = NodeStatus(d.get("status", "idle"))
        return node

    @classmethod
    def register(cls, node_cls: type[Node]) -> None:
        """Register a Node subclass so from_dict can reconstruct it."""
        _NODE_REGISTRY[node_cls.node_type] = node_cls


_NODE_REGISTRY: dict[str, type[Node]] = {}
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_pipeline/test_node.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/node.py tests/test_pipeline/test_node.py
git commit -m "feat: add Node base class - state machine, run(), cache_key(), serialization

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Edge (`edge.py`)

**Files:**
- Create: `app/pipeline/edge.py`
- Create: `tests/test_pipeline/test_edge.py`

- [ ] **Step 1: 写 Edge 测试**

在 `tests/test_pipeline/test_edge.py`:

```python
import pytest

from app.pipeline.edge import Edge


class TestEdge:
    def test_create_edge(self):
        edge = Edge(
            source_node_id="n1",
            source_port="sum",
            target_node_id="n2",
            target_port="value",
        )
        assert edge.source_node_id == "n1"
        assert edge.source_port == "sum"
        assert edge.target_node_id == "n2"
        assert edge.target_port == "value"

    def test_edges_with_same_values_are_equal(self):
        a = Edge("n1", "out", "n2", "in")
        b = Edge("n1", "out", "n2", "in")
        assert a == b

    def test_edges_are_hashable(self):
        edge = Edge("n1", "out", "n2", "in")
        d = {edge: "connection"}
        assert d[edge] == "connection"

    def test_to_dict(self):
        edge = Edge("n1", "sum", "n2", "value")
        d = edge.to_dict()
        assert d == {
            "source_node_id": "n1",
            "source_port": "sum",
            "target_node_id": "n2",
            "target_port": "value",
        }

    def test_from_dict(self):
        d = {
            "source_node_id": "n1",
            "source_port": "out",
            "target_node_id": "n2",
            "target_port": "in",
        }
        edge = Edge.from_dict(d)
        assert edge.source_node_id == "n1"
        assert edge.source_port == "out"
        assert edge.target_node_id == "n2"
        assert edge.target_port == "in"

    def test_is_compatible_checks_port_types(self):
        from app.pipeline.types import PortSpec, PortType

        # Same types are compatible
        out_spec = PortSpec(name="video", port_type=PortType.FILE_PATH)
        in_spec = PortSpec(name="input_video", port_type=PortType.FILE_PATH)
        assert Edge.is_compatible(out_spec, in_spec) is True

        # Different types are not compatible
        srt_spec = PortSpec(name="srt", port_type=PortType.SRT_CONTENT)
        assert Edge.is_compatible(out_spec, srt_spec) is False
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_pipeline/test_edge.py -v
```
Expected: all FAIL

- [ ] **Step 3: 实现 `app/pipeline/edge.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.pipeline.types import PortSpec


@dataclass(frozen=True)
class Edge:
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "source_port": self.source_port,
            "target_node_id": self.target_node_id,
            "target_port": self.target_port,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Edge:
        return cls(
            source_node_id=d["source_node_id"],
            source_port=d["source_port"],
            target_node_id=d["target_node_id"],
            target_port=d["target_port"],
        )

    @staticmethod
    def is_compatible(source_port: PortSpec, target_port: PortSpec) -> bool:
        """Check if two ports have compatible types."""
        return source_port.port_type == target_port.port_type
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_pipeline/test_edge.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/edge.py tests/test_pipeline/test_edge.py
git commit -m "feat: add Edge - directed connection between node ports, type checking

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Graph (`graph.py`)

**Files:**
- Create: `app/pipeline/graph.py`
- Create: `tests/test_pipeline/test_graph.py`

- [ ] **Step 1: 写 Graph 测试**

在 `tests/test_pipeline/test_graph.py`:

```python
import json

import pytest

from app.pipeline.node import Node
from app.pipeline.edge import Edge
from app.pipeline.graph import Graph
from app.pipeline.types import NodeStatus, PortSpec, PortType, ParamSpec, NodeResult


class StepNode(Node):
    """Node with one input and one output of JSON_DATA type."""
    node_type = "Step"

    def _define(self):
        self.inputs = {"in": PortSpec(name="in", port_type=PortType.JSON_DATA)}
        self.outputs = {"out": PortSpec(name="out", port_type=PortType.JSON_DATA)}
        self.params = {}

    async def run(self, inputs, params, work_dir):
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"out": inputs["in"]},
        )


class SourceNode(Node):
    """Node with no inputs, one output."""
    node_type = "Source"

    def _define(self):
        self.inputs = {}
        self.outputs = {"data": PortSpec(name="data", port_type=PortType.JSON_DATA)}
        self.params = {"seed": ParamSpec(name="seed", param_type="int", default=0)}

    async def run(self, inputs, params, work_dir):
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"data": params.get("seed", 0)},
        )


class SinkNode(Node):
    """Node with one input, no outputs."""
    node_type = "Sink"

    def _define(self):
        self.inputs = {"in": PortSpec(name="in", port_type=PortType.JSON_DATA)}
        self.outputs = {}
        self.params = {}

    async def run(self, inputs, params, work_dir):
        return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})


Node.register(StepNode)
Node.register(SourceNode)
Node.register(SinkNode)


class TestGraph:
    def test_empty_graph(self):
        g = Graph()
        assert g.nodes == {}
        assert g.edges == []
        assert g.validate() == []

    def test_add_node(self):
        g = Graph()
        node = SourceNode(label="src")
        g.add_node(node)
        assert node.id in g.nodes
        assert g.nodes[node.id] is node

    def test_add_edge(self):
        g = Graph()
        src = SourceNode()
        sink = SinkNode()
        g.add_node(src)
        g.add_node(sink)
        edge = Edge(src.id, "data", sink.id, "in")
        g.add_edge(edge)
        assert edge in g.edges

    def test_add_edge_rejects_unknown_nodes(self):
        g = Graph()
        src = SourceNode()
        g.add_node(src)
        with pytest.raises(ValueError, match="not in graph"):
            g.add_edge(Edge(src.id, "data", "nonexistent", "in"))
        with pytest.raises(ValueError, match="not in graph"):
            g.add_edge(Edge("nonexistent", "data", src.id, "in"))

    def test_add_edge_rejects_unknown_ports(self):
        g = Graph()
        src = SourceNode()
        sink = SinkNode()
        g.add_node(src)
        g.add_node(sink)
        with pytest.raises(ValueError, match="has no output port"):
            g.add_edge(Edge(src.id, "wrong_port", sink.id, "in"))
        with pytest.raises(ValueError, match="has no input port"):
            g.add_edge(Edge(src.id, "data", sink.id, "wrong_port"))

    def test_add_edge_rejects_type_mismatch(self):
        g = Graph()
        # Create nodes with incompatible port types
        class IntNode(Node):
            node_type = "IntNode"

            def _define(self):
                self.inputs = {}
                self.outputs = {"val": PortSpec(name="val", port_type=PortType.FILE_PATH)}
                self.params = {}

            async def run(self, inputs, params, work_dir):
                return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={"val": "/tmp/test.mp4"})

        class StrNode(Node):
            node_type = "StrNode"

            def _define(self):
                self.inputs = {"val": PortSpec(name="val", port_type=PortType.SRT_CONTENT)}
                self.outputs = {}
                self.params = {}

            async def run(self, inputs, params, work_dir):
                return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})

        src = IntNode()
        dst = StrNode()
        g.add_node(src)
        g.add_node(dst)
        with pytest.raises(ValueError, match="type mismatch"):
            g.add_edge(Edge(src.id, "val", dst.id, "val"))

    def test_topological_order_linear_chain(self):
        g = Graph()
        a = SourceNode()
        b = StepNode()
        c = StepNode()
        d = SinkNode()
        for node in [a, b, c, d]:
            g.add_node(node)
        g.add_edge(Edge(a.id, "data", b.id, "in"))
        g.add_edge(Edge(b.id, "out", c.id, "in"))
        g.add_edge(Edge(c.id, "out", d.id, "in"))

        order = g.topological_order()
        assert len(order) == 4
        assert order.index(a.id) < order.index(b.id)
        assert order.index(b.id) < order.index(c.id)
        assert order.index(c.id) < order.index(d.id)

    def test_topological_order_independent_branches(self):
        g = Graph()
        src = SourceNode()
        left = StepNode()
        right = StepNode()
        g.add_node(src)
        g.add_node(left)
        g.add_node(right)
        g.add_edge(Edge(src.id, "data", left.id, "in"))
        g.add_edge(Edge(src.id, "data", right.id, "in"))

        order = g.topological_order()
        assert order[0] == src.id
        assert set(order[1:]) == {left.id, right.id}

    def test_topological_order_cycle_detection(self):
        g = Graph()
        a = StepNode()
        b = StepNode()
        g.add_node(a)
        g.add_node(b)
        g.add_edge(Edge(a.id, "out", b.id, "in"))
        g.add_edge(Edge(b.id, "out", a.id, "in"))

        with pytest.raises(ValueError, match="cycle"):
            g.topological_order()

    def test_topological_order_disconnected_nodes(self):
        g = Graph()
        a = SourceNode()
        b = SourceNode()
        g.add_node(a)
        g.add_node(b)

        order = g.topological_order()
        assert len(order) == 2
        assert set(order) == {a.id, b.id}

    def test_validate_empty_graph(self):
        g = Graph()
        assert g.validate() == []

    def test_validate_all_inputs_satisfied(self):
        g = Graph()
        src = SourceNode()
        sink = SinkNode()
        g.add_node(src)
        g.add_node(sink)
        g.add_edge(Edge(src.id, "data", sink.id, "in"))
        assert g.validate() == []

    def test_validate_unconnected_required_input(self):
        g = Graph()
        sink = SinkNode()
        g.add_node(sink)
        errors = g.validate()
        assert len(errors) > 0
        assert any("unconnected" in err.lower() for err in errors)

    def test_validate_optional_input_not_required(self):
        g = Graph()
        # Create a node with an optional input
        class OptNode(Node):
            node_type = "Opt"
            def _define(self):
                self.inputs = {"in": PortSpec(name="in", port_type=PortType.JSON_DATA, required=False)}
                self.outputs = {}
                self.params = {}
            async def run(self, inputs, params, work_dir):
                return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})

        node = OptNode()
        g.add_node(node)
        assert g.validate() == []

    def test_to_json_and_from_json(self):
        g = Graph(
            template_id="test_template",
            metadata={"name": "Test Graph", "description": "A test"},
        )
        src = SourceNode(label="source")
        sink = SinkNode(label="sink")
        g.add_node(src)
        g.add_node(sink)
        g.add_edge(Edge(src.id, "data", sink.id, "in"))

        json_str = g.to_json()
        data = json.loads(json_str)

        assert data["template_id"] == "test_template"
        assert data["metadata"]["name"] == "Test Graph"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

        g2 = Graph.from_json(json_str)
        assert g2.template_id == "test_template"
        assert len(g2.nodes) == 2
        assert len(g2.edges) == 1
        assert g2.nodes[src.id].type == "Source"
        assert g2.nodes[sink.id].type == "Sink"

    def test_from_json_preserves_node_positions(self):
        g = Graph()
        src = SourceNode(label="src", x=42, y=99)
        g.add_node(src)

        json_str = g.to_json()
        g2 = Graph.from_json(json_str)
        assert g2.nodes[src.id].x == 42
        assert g2.nodes[src.id].y == 99

    def test_find_downstream_nodes(self):
        g = Graph()
        a = SourceNode()
        b = StepNode()
        c = StepNode()
        d = SinkNode()
        for node in [a, b, c, d]:
            g.add_node(node)
        g.add_edge(Edge(a.id, "data", b.id, "in"))
        g.add_edge(Edge(b.id, "out", c.id, "in"))
        g.add_edge(Edge(c.id, "out", d.id, "in"))

        downstream = g.downstream_of(b.id)
        assert c.id in downstream
        assert d.id in downstream
        assert a.id not in downstream
        assert b.id not in downstream
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_pipeline/test_graph.py -v
```
Expected: all FAIL

- [ ] **Step 3: 实现 `app/pipeline/graph.py`**

```python
from __future__ import annotations

import json
from collections import deque
from typing import Any

from app.pipeline.node import Node
from app.pipeline.edge import Edge


class Graph:
    def __init__(
        self,
        nodes: dict[str, Node] | None = None,
        edges: list[Edge] | None = None,
        template_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.nodes: dict[str, Node] = nodes or {}
        self.edges: list[Edge] = edges or []
        self.template_id = template_id
        self.metadata = metadata or {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.source_node_id not in self.nodes:
            raise ValueError(f"source node '{edge.source_node_id}' not in graph")
        if edge.target_node_id not in self.nodes:
            raise ValueError(f"target node '{edge.target_node_id}' not in graph")

        source_node = self.nodes[edge.source_node_id]
        target_node = self.nodes[edge.target_node_id]

        if edge.source_port not in source_node.outputs:
            raise ValueError(
                f"source node '{edge.source_node_id}' has no output port '{edge.source_port}'"
            )
        if edge.target_port not in target_node.inputs:
            raise ValueError(
                f"target node '{edge.target_node_id}' has no input port '{edge.target_port}'"
            )

        source_spec = source_node.outputs[edge.source_port]
        target_spec = target_node.inputs[edge.target_port]
        if not Edge.is_compatible(source_spec, target_spec):
            raise ValueError(
                f"type mismatch: {edge.source_node_id}.{edge.source_port} "
                f"({source_spec.port_type.value}) → "
                f"{edge.target_node_id}.{edge.target_port} "
                f"({target_spec.port_type.value})"
            )

        self.edges.append(edge)

    def topological_order(self) -> list[str]:
        """Return node IDs in topological order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for edge in self.edges:
            adjacency[edge.source_node_id].append(edge.target_node_id)
            in_degree[edge.target_node_id] += 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        result = []

        while queue:
            nid = queue.popleft()
            result.append(nid)
            for neighbor in adjacency[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise ValueError(f"graph contains a cycle; {len(self.nodes) - len(result)} nodes unreachable")

        return result

    def downstream_of(self, node_id: str) -> set[str]:
        """Return all node IDs that are transitively downstream of node_id."""
        adjacency: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for edge in self.edges:
            adjacency[edge.source_node_id].append(edge.target_node_id)

        visited: set[str] = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list means valid."""
        errors = []
        for node_id, node in self.nodes.items():
            for port_name, port_spec in node.inputs.items():
                if not port_spec.required:
                    continue
                connected = any(
                    edge.target_node_id == node_id and edge.target_port == port_name
                    for edge in self.edges
                )
                if not connected:
                    errors.append(
                        f"required input '{port_name}' of node '{node_id}' ({node.label}) is unconnected"
                    )
        return errors

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "metadata": self.metadata,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @staticmethod
    def from_json(json_str: str) -> Graph:
        data = json.loads(json_str)
        return Graph.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Graph:
        nodes = {}
        for node_data in data.get("nodes", []):
            node = Node.from_dict(node_data)
            nodes[node.id] = node
        edges = [Edge.from_dict(e) for e in data.get("edges", [])]
        return Graph(
            nodes=nodes,
            edges=edges,
            template_id=data.get("template_id"),
            metadata=data.get("metadata", {}),
        )
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_pipeline/test_graph.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/graph.py tests/test_pipeline/test_graph.py
git commit -m "feat: add Graph - node collection, topological sort, JSON serialization, cycle detection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Executor (`executor.py`)

**Files:**
- Create: `app/pipeline/executor.py`
- Create: `tests/test_pipeline/test_executor.py`

- [ ] **Step 1: 写 Executor 测试**

在 `tests/test_pipeline/test_executor.py`:

```python
import asyncio
from pathlib import Path

import pytest

from app.pipeline.node import Node
from app.pipeline.edge import Edge
from app.pipeline.graph import Graph
from app.pipeline.executor import Executor
from app.pipeline.types import NodeStatus, PortSpec, PortType, ParamSpec, NodeResult, ExecutorEvent


class EchoNode(Node):
    """Node that passes input to output, recording that it ran."""
    node_type = "Echo"
    run_count = 0

    def _define(self):
        self.inputs = {"value": PortSpec(name="value", port_type=PortType.JSON_DATA)}
        self.outputs = {"echo": PortSpec(name="echo", port_type=PortType.JSON_DATA)}
        self.params = {
            "suffix": ParamSpec(name="suffix", param_type="string", default=""),
        }

    async def run(self, inputs, params, work_dir):
        EchoNode.run_count += 1
        value = inputs["value"]
        suffix = params.get("suffix", "")
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"echo": f"{value}{suffix}"},
        )


class SourceNode(Node):
    node_type = "Source"

    def _define(self):
        self.inputs = {}
        self.outputs = {"data": PortSpec(name="data", port_type=PortType.JSON_DATA)}
        self.params = {"value": ParamSpec(name="value", param_type="string", default="hello")}

    async def run(self, inputs, params, work_dir):
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"data": params.get("value", "hello")},
        )


class FatalNode(Node):
    node_type = "Fatal"

    def _define(self):
        self.inputs = {"in": PortSpec(name="in", port_type=PortType.JSON_DATA)}
        self.outputs = {}
        self.params = {}

    async def run(self, inputs, params, work_dir):
        raise RuntimeError("FatalNode always fails")


Node.register(EchoNode)
Node.register(SourceNode)
Node.register(FatalNode)


def build_linear_graph():
    """Source → Echo → Echo"""
    g = Graph(metadata={"name": "linear test"})
    src = SourceNode(label="src")
    a = EchoNode(label="echo-a")
    b = EchoNode(label="echo-b")
    g.add_node(src)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(Edge(src.id, "data", a.id, "value"))
    g.add_edge(Edge(a.id, "echo", b.id, "value"))
    return g


class TestExecutor:
    @pytest.mark.asyncio
    async def test_run_linear_graph(self, tmp_path):
        g = build_linear_graph()
        events = []
        async def collect(event):
            events.append(event)

        executor = Executor(cache_dir=tmp_path / "cache", progress_callback=collect)
        result = await executor.run(g)
        assert result.success is True
        assert len(result.node_results) == 3

        # Check all nodes succeeded
        assert all(nr.success for nr in result.node_results)

        # Check final output
        assert result.outputs[b.id]["echo"] == "hello"

        # Check events
        status_events = [e for e in events if e.event_type == "node_status"]
        done_events = [e for e in events if e.event_type == "node_done"]
        assert len(done_events) == 3
        assert any(e.event_type == "graph_complete" for e in events)

    @pytest.mark.asyncio
    async def test_executor_result_structure(self, tmp_path):
        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        result = await executor.run(g)

        # Every node in the graph has a corresponding NodeResult
        node_ids_in_graph = set(g.nodes.keys())
        node_ids_in_results = {nr.node_id for nr in result.node_results}
        assert node_ids_in_graph == node_ids_in_results

        # All results have outputs
        for nr in result.node_results:
            assert isinstance(nr.outputs, dict)

    @pytest.mark.asyncio
    async def test_graph_validation_fails_before_execution(self, tmp_path):
        g = Graph()
        # Sink with required input, not connected
        sink = EchoNode()
        g.add_node(sink)

        executor = Executor(cache_dir=tmp_path / "cache")
        with pytest.raises(ValueError, match="validation"):
            await executor.run(g)

    @pytest.mark.asyncio
    async def test_error_strategy_stop(self, tmp_path):
        g = Graph()
        src = SourceNode()
        fatal = FatalNode()
        after = EchoNode()
        g.add_node(src)
        g.add_node(fatal)
        g.add_node(after)
        g.add_edge(Edge(src.id, "data", fatal.id, "in"))
        g.add_edge(Edge(fatal.id, "in", after.id, "value"))  # won't matter

        events = []
        executor = Executor(
            cache_dir=tmp_path / "cache",
            progress_callback=lambda e: events.append(e),
            error_strategy="stop",
        )
        result = await executor.run(g)
        assert result.success is False
        assert any(nr.status == NodeStatus.FAILED for nr in result.node_results)
        assert any(nr.status == NodeStatus.SKIPPED for nr in result.node_results)
        error_events = [e for e in events if e.event_type == "node_error"]
        assert len(error_events) >= 1

    @pytest.mark.asyncio
    async def test_caching_skips_unchanged_nodes(self, tmp_path):
        EchoNode.run_count = 0

        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        result1 = await executor.run(g)
        assert result1.success is True
        first_run_count = EchoNode.run_count

        # Run same graph again — should hit cache
        g2 = build_linear_graph()
        # Same node IDs for cache to work
        for n in g2.nodes.values():
            old = g.nodes.get(n.id)
            if old:
                n.id = old.id
        executor2 = Executor(cache_dir=tmp_path / "cache")
        result2 = await executor2.run(g2)
        assert result2.success is True
        # No additional runs because cache hit
        assert EchoNode.run_count == first_run_count

    @pytest.mark.asyncio
    async def test_changed_param_bypasses_cache(self, tmp_path):
        EchoNode.run_count = 0

        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        result1 = await executor.run(g)
        first_run_count = EchoNode.run_count

        # Change a param
        g2 = build_linear_graph()
        for n in g2.nodes.values():
            old = g.nodes.get(n.id)
            if old:
                n.id = old.id
        # Modify the suffix param of the first Echo node
        for node in g2.nodes.values():
            if node.label == "echo-a":
                node.params["suffix"] = ParamSpec(name="suffix", param_type="string", default="!")
                break

        executor2 = Executor(cache_dir=tmp_path / "cache")
        result2 = await executor2.run(g2)
        # Cache miss on the changed node and downstream
        assert EchoNode.run_count > first_run_count

    @pytest.mark.asyncio
    async def test_force_rerun_ignores_cache(self, tmp_path):
        EchoNode.run_count = 0

        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        await executor.run(g)
        first_run_count = EchoNode.run_count

        # Same graph, force rerun
        g2 = build_linear_graph()
        for n in g2.nodes.values():
            old = g.nodes.get(n.id)
            if old:
                n.id = old.id

        executor2 = Executor(cache_dir=tmp_path / "cache", force_rerun=True)
        await executor2.run(g2)
        assert EchoNode.run_count > first_run_count


    @pytest.mark.asyncio
    async def test_executor_result_to_dict(self, tmp_path):
        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        result = await executor.run(g)

        d = result.to_dict()
        assert d["success"] is True
        assert len(d["node_results"]) == 3
        assert "total_duration_ms" in d

    @pytest.mark.asyncio
    async def test_executor_collects_inputs_from_upstream(self, tmp_path):
        g = Graph()
        src = SourceNode(label="src")
        src.params["value"] = ParamSpec(name="value", param_type="string", default="world")
        echo = EchoNode(label="echo")
        g.add_node(src)
        g.add_node(echo)
        g.add_edge(Edge(src.id, "data", echo.id, "value"))

        executor = Executor(cache_dir=tmp_path / "cache")
        result = await executor.run(g)
        assert result.success is True
        # The echo node should have received "world" from source
        assert result.outputs[echo.id]["echo"] == "world"
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_pipeline/test_executor.py -v
```
Expected: all FAIL

- [ ] **Step 3: 实现 `app/pipeline/executor.py`**

```python
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Awaitable

from app.pipeline.node import Node
from app.pipeline.graph import Graph
from app.pipeline.types import ExecutorEvent, NodeResult, NodeStatus


class ExecutorResult:
    def __init__(
        self,
        success: bool,
        node_results: list[NodeResult],
        outputs: dict[str, dict[str, Any]],
        total_duration_ms: float = 0.0,
    ):
        self.success = success
        self.node_results = node_results
        self.outputs = outputs
        self.total_duration_ms = total_duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "node_results": [r.to_dict() for r in self.node_results],
            "outputs": self.outputs,
            "total_duration_ms": self.total_duration_ms,
        }


class Executor:
    def __init__(
        self,
        cache_dir: Path | None = None,
        progress_callback: Callable[[ExecutorEvent], Awaitable[None]] | None = None,
        error_strategy: str = "stop",
        force_rerun: bool = False,
    ):
        self.cache_dir = cache_dir or Path(".data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback
        self.error_strategy = error_strategy
        self.force_rerun = force_rerun

    async def run(self, graph: Graph) -> ExecutorResult:
        errors = graph.validate()
        if errors:
            raise ValueError(f"graph validation failed: {'; '.join(errors)}")

        try:
            order = graph.topological_order()
        except ValueError as e:
            raise ValueError(f"graph validation failed: {e}") from e

        all_outputs: dict[str, dict[str, Any]] = {}
        node_results: list[NodeResult] = []
        start_time = time.monotonic()

        for node_id in order:
            node = graph.nodes[node_id]

            # Collect inputs from upstream nodes
            inputs = self._resolve_inputs(node, graph, all_outputs)

            # Collect params (merge param spec defaults with any overrides)
            params = {
                name: spec.default
                for name, spec in node.params.items()
            }

            # Check cache
            cache_key = node.cache_key(inputs, params)
            if not self.force_rerun and self._cache_hit(node, cache_key):
                cached_outputs = self._load_cache(node, cache_key)
                all_outputs[node_id] = cached_outputs
                await self._emit(ExecutorEvent.node_status(node_id, NodeStatus.DONE, 1.0))
                await self._emit(ExecutorEvent.node_done(node_id, cached_outputs))
                node_results.append(NodeResult(
                    node_id=node_id,
                    status=NodeStatus.DONE,
                    outputs=cached_outputs,
                ))
                continue

            # Execute
            await self._emit(ExecutorEvent.node_status(node_id, NodeStatus.RUNNING, 0.0))
            work_dir = self.cache_dir / node.type / cache_key
            work_dir.mkdir(parents=True, exist_ok=True)

            try:
                result = await node.execute(inputs, params, work_dir)
                all_outputs[node_id] = result.outputs
                self._save_cache(node, cache_key, result.outputs)
                node_results.append(result)
                await self._emit(ExecutorEvent.node_status(node_id, NodeStatus.DONE, 1.0))
                await self._emit(ExecutorEvent.node_done(node_id, result.outputs))
            except Exception as exc:
                node_results.append(NodeResult(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    outputs={},
                    error=str(exc),
                ))
                await self._emit(ExecutorEvent.node_error(node_id, str(exc)))
                await self._emit(ExecutorEvent.log(node_id, "error", str(exc)))

                if self.error_strategy == "stop":
                    # Mark remaining nodes as skipped
                    remaining = order[order.index(node_id) + 1:]
                    for rid in remaining:
                        node_results.append(NodeResult(
                            node_id=rid,
                            status=NodeStatus.SKIPPED,
                            outputs={},
                            error="skipped due to upstream failure",
                        ))
                    break
                else:
                    continue

        total_ms = (time.monotonic() - start_time) * 1000
        success = all(
            nr.status in (NodeStatus.DONE, NodeStatus.SKIPPED)
            for nr in node_results
        )

        final_outputs = {
            nid: outputs
            for nid, outputs in all_outputs.items()
        }

        await self._emit(ExecutorEvent.graph_complete("", final_outputs))
        return ExecutorResult(
            success=success,
            node_results=node_results,
            outputs=final_outputs,
            total_duration_ms=total_ms,
        )

    def _resolve_inputs(
        self,
        node: Node,
        graph: Graph,
        all_outputs: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        inputs = {}
        for port_name, port_spec in node.inputs.items():
            for edge in graph.edges:
                if edge.target_node_id == node.id and edge.target_port == port_name:
                    upstream_outputs = all_outputs.get(edge.source_node_id, {})
                    if edge.source_port in upstream_outputs:
                        inputs[port_name] = upstream_outputs[edge.source_port]
                    break
        return inputs

    async def _emit(self, event: ExecutorEvent) -> None:
        if self.progress_callback:
            await self.progress_callback(event)

    def _cache_path(self, node: Node, cache_key: str) -> Path:
        return self.cache_dir / node.type / cache_key

    def _cache_hit(self, node: Node, cache_key: str) -> bool:
        output_file = self._cache_path(node, cache_key) / "outputs.json"
        return output_file.exists()

    def _load_cache(self, node: Node, cache_key: str) -> dict[str, Any]:
        output_file = self._cache_path(node, cache_key) / "outputs.json"
        return json.loads(output_file.read_text("utf-8"))

    def _save_cache(self, node: Node, cache_key: str, outputs: dict[str, Any]) -> None:
        cache_path = self._cache_path(node, cache_key)
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / "outputs.json").write_text(
            json.dumps(outputs, indent=2, ensure_ascii=False), "utf-8"
        )
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_pipeline/test_executor.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/executor.py tests/test_pipeline/test_executor.py
git commit -m "feat: add Executor - graph execution, content-addressed caching, progress events

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 更新 `__init__.py` 并运行全部测试

**Files:**
- Modify: `app/pipeline/__init__.py`

- [ ] **Step 1: 确认 `__init__.py` 包含所有新符号**

`app/pipeline/__init__.py` 已经在 Task 1 Step 5 中写好，包含了所有符号。确认内容:

```python
from app.pipeline.types import (
    ExecutorEvent,
    NodeResult,
    NodeStatus,
    ParamSpec,
    PortSpec,
    PortType,
)
from app.pipeline.node import Node
from app.pipeline.edge import Edge
from app.pipeline.graph import Graph
from app.pipeline.executor import Executor

__all__ = [
    "Node",
    "Edge",
    "Graph",
    "Executor",
    "PortType",
    "PortSpec",
    "ParamSpec",
    "NodeStatus",
    "NodeResult",
    "ExecutorEvent",
]
```

- [ ] **Step 2: 运行全部 Pipeline SDK 测试**

```bash
python -m pytest tests/test_pipeline/ -v
```
Expected: all tests PASS (should be ~42 tests across 5 test files)

- [ ] **Step 3: 运行原有测试确保不破坏**

```bash
python -m pytest tests/ -v
```
Expected: all original tests still PASS

- [ ] **Step 4: Commit**

```bash
git add app/pipeline/__init__.py
git commit -m "chore: finalize Pipeline SDK __init__.py exports

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 验收标准

Phase 1 完成后，以下应该可以正常工作:

```python
import asyncio
from pathlib import Path
from app.pipeline import Graph, Executor, Node, Edge, PortSpec, PortType, ParamSpec, NodeStatus, NodeResult

class TestNode(Node):
    node_type = "Test"
    def _define(self):
        self.inputs = {}
        self.outputs = {"result": PortSpec(name="result", port_type=PortType.JSON_DATA)}
        self.params = {"message": ParamSpec(name="message", param_type="string", default="hello")}
    async def run(self, inputs, params, work_dir):
        (work_dir / "output.txt").write_text(params["message"])
        return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={"result": params["message"]})

Node.register(TestNode)

async def demo():
    g = Graph()
    node = TestNode(label="demo")
    g.add_node(node)

    executor = Executor(cache_dir=Path("/tmp/pipeline_demo"))
    result = await executor.run(g)
    print(result.to_dict())

asyncio.run(demo())
```
