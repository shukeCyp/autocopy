from __future__ import annotations

import json
import subprocess
import time
import traceback
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

            # Collect params (merge param spec defaults)
            params = {
                name: spec.default
                for name, spec in node.params.items()
            }

            await self._emit(ExecutorEvent.node_executing(node_id))
            validation_issues = node.validate(inputs, params)
            validation_errors = [issue for issue in validation_issues if issue.level == "error"]
            if validation_errors:
                error = "; ".join(issue.message for issue in validation_errors)
                node.status = NodeStatus.FAILED
                node_results.append(NodeResult(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    outputs={},
                    error=error,
                    validation_issues=validation_issues,
                ))
                await self._emit(ExecutorEvent.node_error(node_id, error, validation_issues))
                await self._emit(ExecutorEvent.log(node_id, "error", error))

                if self.error_strategy == "stop":
                    remaining = order[order.index(node_id) + 1:]
                    for rid in remaining:
                        node_results.append(NodeResult(
                            node_id=rid,
                            status=NodeStatus.SKIPPED,
                            outputs={},
                            error="skipped due to upstream failure",
                        ))
                    break
                continue

            # Check cache
            cache_key = node.cache_key(inputs, params)
            if not self.force_rerun and self._cache_hit(node, cache_key):
                cached_outputs = self._load_cache(node, cache_key)
                all_outputs[node_id] = cached_outputs
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
                await self._emit(ExecutorEvent.node_done(node_id, result.outputs))
            except Exception as exc:
                error = str(exc)
                detail = self._format_exception(exc)
                node_results.append(NodeResult(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    outputs={},
                    error=error,
                ))
                await self._emit(ExecutorEvent.node_error(node_id, error))
                await self._emit(ExecutorEvent.log(node_id, "error", detail))

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
        for port_name in node.inputs:
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

    def _format_exception(self, exc: Exception) -> str:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        if isinstance(exc, subprocess.CalledProcessError):
            parts = [detail]
            if exc.stdout:
                parts.append(f"\nstdout:\n{self._decode_process_output(exc.stdout)}")
            if exc.stderr:
                parts.append(f"\nstderr:\n{self._decode_process_output(exc.stderr)}")
            return "\n".join(parts).rstrip()
        return detail

    def _decode_process_output(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").rstrip()
        return str(value).rstrip()

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
