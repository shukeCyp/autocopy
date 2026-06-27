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

    def __init_subclass__(cls, **kwargs):
        """Automatically wrap run() so that the DONE status transition is
        part of the call chain visible inside run() itself.
        """
        super().__init_subclass__(**kwargs)
        original_run = cls.run
        # Guard against re-wrapping if a further subclass inherits a wrapped run.
        if getattr(original_run, '_node_run_wrapped', False):
            return

        async def wrapped_run(self, inputs, params, work_dir):
            result = await original_run(self, inputs, params, work_dir)
            self.status = NodeStatus.DONE
            return result

        wrapped_run._node_run_wrapped = True
        cls.run = wrapped_run

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
