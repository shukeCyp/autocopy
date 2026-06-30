from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, ValidationIssue
from app.pipeline.validation import RequiredInputRule, RequiredParamRule, ValidationRule


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

    def schema(self) -> dict[str, Any]:
        """Return the node's reusable runtime contract for frontend/editor use."""
        return {
            "id": self.node_type,
            "type": self.node_type,
            "label": self.label,
            "inputs": {name: spec.to_dict() for name, spec in self.inputs.items()},
            "outputs": {name: spec.to_dict() for name, spec in self.outputs.items()},
            "params": {name: spec.to_dict() for name, spec in self.params.items()},
        }

    def validation_rules(self) -> list[ValidationRule]:
        """Rules shared by every node. Subclasses append domain rules."""
        return [
            RequiredInputRule(),
            RequiredParamRule(),
            *self.custom_validation_rules(),
        ]

    def custom_validation_rules(self) -> list[ValidationRule]:
        return []

    def validate(self, inputs: dict[str, Any], params: dict[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for rule in self.validation_rules():
            issues.extend(rule.validate(self, inputs, params))
        issues.extend(self.validate_custom(inputs, params))
        return issues

    def validate_custom(
        self,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        return []

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

        Looks up the concrete subclass in _NODE_REGISTRY by d['type'].
        Raises ValueError if the type is not registered.
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
        for name, saved_spec in d.get("params", {}).items():
            if name not in node.params or not isinstance(saved_spec, dict):
                continue
            current = node.params[name]
            node.params[name] = ParamSpec(
                name=current.name,
                param_type=current.param_type,
                default=saved_spec.get("default", current.default),
                description=current.description,
                options=current.options,
                required=saved_spec.get("required", current.required),
            )
        return node

    @classmethod
    def register(cls, node_cls: type[Node]) -> None:
        """Register a Node subclass so from_dict can reconstruct it."""
        _NODE_REGISTRY[node_cls.node_type] = node_cls


_NODE_REGISTRY: dict[str, type[Node]] = {}


def registered_node_classes() -> dict[str, type[Node]]:
    return dict(_NODE_REGISTRY)
