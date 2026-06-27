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
