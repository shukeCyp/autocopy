import json

from app.server.workflow_templates import upgrade_workflow_graph_json


def test_upgrade_workflow_graph_json_replaces_vmf_auto_model():
    graph = {
        "nodes": [
            {
                "id": "vmf",
                "type": "VideoMatchVMF",
                "params": {
                    "model": {
                        "name": "model",
                        "param_type": "select",
                        "default": "auto",
                        "options": ["auto", "dinov2_vits14", "dinov2_vitb14"],
                    }
                },
            }
        ],
        "edges": [],
    }

    upgraded = json.loads(upgrade_workflow_graph_json(json.dumps(graph)))
    model_param = upgraded["nodes"][0]["params"]["model"]

    assert model_param["default"] == "dinov2_vits14"
    assert model_param["options"] == ["dinov2_vits14", "dinov2_vitb14"]
