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


class OptInputNode(Node):
    """Node with an optional input."""
    node_type = "OptInput"

    def _define(self):
        self.inputs = {"in": PortSpec(name="in", port_type=PortType.JSON_DATA, required=False)}
        self.outputs = {}
        self.params = {}

    async def run(self, inputs, params, work_dir):
        return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})


Node.register(StepNode)
Node.register(SourceNode)
Node.register(SinkNode)
Node.register(OptInputNode)


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
        src = SourceNode()  # output type: JSON_DATA
        # Create a node with incompatible input port type
        class FileSinkNode(Node):
            node_type = "FileSink"
            def _define(self):
                self.inputs = {"in": PortSpec(name="in", port_type=PortType.FILE_PATH)}
                self.outputs = {}
                self.params = {}
            async def run(self, inputs, params, work_dir):
                return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={})

        Node.register(FileSinkNode)
        sink = FileSinkNode()
        g.add_node(src)
        g.add_node(sink)
        with pytest.raises(ValueError, match="type mismatch"):
            g.add_edge(Edge(src.id, "data", sink.id, "in"))

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
        node = OptInputNode()
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

    def test_downstream_of(self):
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

    def test_downstream_of_leaf_node(self):
        g = Graph()
        src = SourceNode()
        sink = SinkNode()
        g.add_node(src)
        g.add_node(sink)
        g.add_edge(Edge(src.id, "data", sink.id, "in"))

        downstream = g.downstream_of(sink.id)
        assert downstream == set()
