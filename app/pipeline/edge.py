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
