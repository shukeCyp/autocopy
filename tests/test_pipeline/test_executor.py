from pathlib import Path

import pytest

from app.pipeline.node import Node
from app.pipeline.edge import Edge
from app.pipeline.graph import Graph
from app.pipeline.executor import Executor
from app.pipeline.types import NodeStatus, PortSpec, PortType, ParamSpec, NodeResult


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
    """Source -> Echo -> Echo"""
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
        last_node = [n for n in g.nodes.values() if n.label == "echo-b"][0]
        assert result.outputs[last_node.id]["echo"] == "hello"

        # Check events
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
        from app.pipeline.node import Node as N

        class BareNode(N):
            node_type = "Bare"
            def _define(self):
                self.inputs = {"required_in": PortSpec(name="required_in", port_type=PortType.JSON_DATA)}
                self.outputs = {}
                self.params = {}
            async def run(self, inputs, params, work_dir):
                return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})

        N.register(BareNode)
        g.add_node(BareNode())

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
        # Connect after to src so validation passes; after follows fatal in
        # topological order, so it will be skipped when fatal fails
        g.add_edge(Edge(src.id, "data", after.id, "value"))

        events = []

        async def collect(event):
            events.append(event)

        executor = Executor(
            cache_dir=tmp_path / "cache",
            progress_callback=collect,
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

        # Run same graph again -- should hit cache
        g2 = build_linear_graph()
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
        await executor.run(g)
        first_run_count = EchoNode.run_count

        # Change a param on one Echo node
        for node in g.nodes.values():
            if node.label == "echo-a":
                node.params["suffix"] = ParamSpec(name="suffix", param_type="string", default="!")
                break

        executor2 = Executor(cache_dir=tmp_path / "cache")
        await executor2.run(g)
        # Cache miss on the changed node and downstream
        assert EchoNode.run_count > first_run_count

    @pytest.mark.asyncio
    async def test_force_rerun_ignores_cache(self, tmp_path):
        EchoNode.run_count = 0

        g = build_linear_graph()
        executor = Executor(cache_dir=tmp_path / "cache")
        await executor.run(g)
        first_run_count = EchoNode.run_count

        executor2 = Executor(cache_dir=tmp_path / "cache", force_rerun=True)
        await executor2.run(g)
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
        assert result.outputs[echo.id]["echo"] == "world"
