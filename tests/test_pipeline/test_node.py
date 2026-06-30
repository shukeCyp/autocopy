from pathlib import Path

import pytest

from app.pipeline.types import NodeStatus, PortSpec, PortType, ParamSpec, NodeResult
from app.pipeline.node import Node


class AddNode(Node):
    """Test node that adds two numbers."""
    node_type = "Add"

    def _define(self):
        self.inputs = {
            "a": PortSpec(name="a", port_type=PortType.JSON_DATA),
            "b": PortSpec(name="b", port_type=PortType.JSON_DATA),
        }
        self.outputs = {
            "sum": PortSpec(name="sum", port_type=PortType.JSON_DATA),
        }
        self.params = {
            "offset": ParamSpec(name="offset", param_type="int", default=0),
        }

    async def run(self, inputs, params, work_dir):
        a = inputs["a"]
        b = inputs["b"]
        offset = params.get("offset", 0)
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"sum": a + b + offset},
        )


class IdentityNode(Node):
    """Test node that passes input straight through."""
    node_type = "Identity"

    def _define(self):
        self.inputs = {
            "value": PortSpec(name="value", port_type=PortType.JSON_DATA),
        }
        self.outputs = {
            "value": PortSpec(name="value", port_type=PortType.JSON_DATA),
        }
        self.params = {}

    async def run(self, inputs, params, work_dir):
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"value": inputs["value"]},
        )


class FailingNode(Node):
    """Test node that always fails."""
    node_type = "Failing"

    def _define(self):
        self.inputs = {}
        self.outputs = {
            "result": PortSpec(name="result", port_type=PortType.JSON_DATA),
        }
        self.params = {}

    async def run(self, inputs, params, work_dir):
        raise RuntimeError("intentional failure")


Node.register(AddNode)
Node.register(IdentityNode)
Node.register(FailingNode)


class TestNode:
    def test_node_has_unique_id(self):
        a = AddNode(label="adder")
        b = AddNode(label="adder")
        assert a.id != b.id
        assert len(a.id) > 0

    def test_node_type_is_class_attribute(self):
        node = AddNode(label="test")
        assert node.type == "Add"

    def test_node_label(self):
        node = AddNode(label="My Adder")
        assert node.label == "My Adder"

    def test_default_label_is_node_type(self):
        node = IdentityNode()
        assert node.label == "Identity"

    def test_initial_status_is_idle(self):
        node = AddNode()
        assert node.status == NodeStatus.IDLE

    def test_node_has_inputs(self):
        node = AddNode()
        assert "a" in node.inputs
        assert "b" in node.inputs
        assert node.inputs["a"].port_type == PortType.JSON_DATA

    def test_node_has_outputs(self):
        node = AddNode()
        assert "sum" in node.outputs
        assert node.outputs["sum"].port_type == PortType.JSON_DATA

    def test_node_has_params(self):
        node = AddNode()
        assert "offset" in node.params
        assert node.params["offset"].default == 0

    def test_node_schema_serializes_runtime_contract(self):
        node = AddNode(id="add_1", label="Adder", x=12, y=34)

        schema = node.schema()

        assert schema["id"] == "Add"
        assert schema["type"] == "Add"
        assert schema["label"] == "Adder"
        assert schema["inputs"]["a"]["port_type"] == "json_data"
        assert schema["outputs"]["sum"]["port_type"] == "json_data"
        assert schema["params"]["offset"]["param_type"] == "int"
        assert schema["params"]["offset"]["default"] == 0

    def test_validate_reports_missing_required_param(self):
        class RequiredParamNode(AddNode):
            node_type = "RequiredParam"

            def _define(self):
                super()._define()
                self.params["name"] = ParamSpec(name="name", param_type="string", default="", required=True)

        node = RequiredParamNode(id="required")

        issues = node.validate({"a": 1, "b": 2}, {"offset": 0, "name": ""})

        assert [issue.to_dict() for issue in issues] == [
            {
                "level": "error",
                "code": "missing_param",
                "message": "name is required",
                "field": "name",
                "node_id": "required",
            }
        ]

    def test_validate_reports_missing_required_input(self):
        node = AddNode(id="add")

        issues = node.validate({"a": 1}, {"offset": 0})

        assert issues[0].code == "missing_input"
        assert issues[0].field == "b"
        assert issues[0].node_id == "add"

    def test_node_position(self):
        node = AddNode(x=100, y=200)
        assert node.x == 100
        assert node.y == 200

    def test_default_position_is_zero(self):
        node = AddNode()
        assert node.x == 0
        assert node.y == 0

    @pytest.mark.asyncio
    async def test_run_returns_node_result(self, tmp_path):
        node = AddNode()
        result = await node.run({"a": 3, "b": 4}, {"offset": 1}, tmp_path)
        assert result.success is True
        assert result.outputs["sum"] == 8

    @pytest.mark.asyncio
    async def test_run_updates_status(self, tmp_path):
        node = AddNode()
        await node.execute({"a": 1, "b": 2}, {}, tmp_path)
        assert node.status == NodeStatus.DONE

    @pytest.mark.asyncio
    async def test_execute_sets_status_running_during_run(self, tmp_path):
        node = AddNode()
        captured_status = None

        original_run = node.run

        async def tracking_run(inputs, params, work_dir):
            nonlocal captured_status
            captured_status = node.status
            return await original_run(inputs, params, work_dir)

        node.run = tracking_run
        await node.execute({"a": 1, "b": 1}, {}, tmp_path)
        assert captured_status == NodeStatus.RUNNING
        assert node.status == NodeStatus.DONE

    @pytest.mark.asyncio
    async def test_execute_on_failure_sets_status_failed(self, tmp_path):
        node = FailingNode()
        with pytest.raises(RuntimeError):
            await node.execute({}, {}, tmp_path)
        assert node.status == NodeStatus.FAILED

    def test_from_dict_unknown_type_raises(self):
        d = {"id": "n1", "type": "UnknownType", "label": "x", "x": 0, "y": 0, "status": "idle", "inputs": {}, "outputs": {}, "params": {}}
        with pytest.raises(ValueError, match="Unknown node type"):
            Node.from_dict(d)

    def test_cache_key_is_stable(self):
        node = AddNode()
        key1 = node.cache_key({"a": 10, "b": 20}, {"offset": 0})
        key2 = node.cache_key({"a": 10, "b": 20}, {"offset": 0})
        assert key1 == key2

    def test_cache_key_changes_with_different_inputs(self):
        node = AddNode()
        key1 = node.cache_key({"a": 1, "b": 2}, {})
        key2 = node.cache_key({"a": 3, "b": 4}, {})
        assert key1 != key2

    def test_cache_key_changes_with_different_params(self):
        node = AddNode()
        key1 = node.cache_key({"a": 1, "b": 2}, {"offset": 0})
        key2 = node.cache_key({"a": 1, "b": 2}, {"offset": 10})
        assert key1 != key2

    def test_cache_key_includes_node_type(self):
        add = AddNode()
        identity = IdentityNode()
        key1 = add.cache_key({"a": 1, "b": 2}, {})
        key2 = identity.cache_key({"value": {"a": 1, "b": 2}}, {})
        assert key1 != key2

    def test_to_dict(self):
        node = AddNode(label="adder", x=100, y=200)
        d = node.to_dict()
        assert d["id"] == node.id
        assert d["type"] == "Add"
        assert d["label"] == "adder"
        assert d["x"] == 100
        assert d["y"] == 200
        assert d["status"] == "idle"
        assert "a" in d["inputs"]
        assert "b" in d["inputs"]
        assert "sum" in d["outputs"]
        assert "offset" in d["params"]
        assert d["params"]["offset"]["default"] == 0

    def test_from_dict(self):
        d = {
            "id": "n1",
            "type": "Add",
            "label": "adder",
            "x": 42,
            "y": 99,
            "status": "done",
            "inputs": {
                "a": {"name": "a", "port_type": "json_data"},
                "b": {"name": "b", "port_type": "json_data"},
            },
            "outputs": {
                "sum": {"name": "sum", "port_type": "json_data"},
            },
            "params": {
                "offset": {"name": "offset", "param_type": "int", "default": 0},
            },
        }
        node = Node.from_dict(d)
        assert node.id == "n1"
        assert node.type == "Add"
        assert node.label == "adder"
        assert node.x == 42
        assert node.y == 99
        assert node.status == NodeStatus.DONE
        assert node.inputs["a"].port_type == PortType.JSON_DATA
        assert node.outputs["sum"].port_type == PortType.JSON_DATA
        assert node.params["offset"].default == 0

    def test_from_dict_preserves_serialized_param_defaults(self):
        d = {
            "id": "n1",
            "type": "Add",
            "label": "adder",
            "x": 0,
            "y": 0,
            "status": "idle",
            "inputs": {},
            "outputs": {},
            "params": {
                "offset": {"name": "offset", "param_type": "int", "default": 10},
            },
        }

        node = Node.from_dict(d)

        assert node.params["offset"].default == 10
