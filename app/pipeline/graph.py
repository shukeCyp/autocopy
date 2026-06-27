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
            raise ValueError(
                f"graph contains a cycle; {len(self.nodes) - len(result)} nodes unreachable"
            )

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
