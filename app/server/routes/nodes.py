from __future__ import annotations

import importlib

from fastapi import APIRouter, HTTPException

from app.pipeline.node import Node, registered_node_classes

router = APIRouter(prefix="/api/nodes", tags=["nodes"])

# Ensure node registration happens before the registry is read.
_registered_nodes_module = importlib.import_module("app.nodes")


def _public_node_types() -> list[str]:
    node_types: list[str] = []
    for name in getattr(_registered_nodes_module, "__all__", []):
        value = getattr(_registered_nodes_module, name, None)
        if isinstance(value, type) and issubclass(value, Node):
            node_types.append(value.node_type)
    return node_types


def _node_schema(node_type: str) -> dict:
    if node_type not in set(_public_node_types()):
        raise HTTPException(status_code=404, detail=f"unknown node type: {node_type}")
    node_cls = registered_node_classes().get(node_type)
    if node_cls is None:
        raise HTTPException(status_code=404, detail=f"unknown node type: {node_type}")
    return node_cls().schema()


@router.get("")
async def list_node_schemas() -> list[dict]:
    return [
        _node_schema(node_type)
        for node_type in sorted(_public_node_types())
    ]


@router.get("/{node_type}")
async def get_node_schema(node_type: str) -> dict:
    return _node_schema(node_type)
