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
