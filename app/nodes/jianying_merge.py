from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType


class JianyingMerge(Node):
    """Create a Jianying draft from frame-match segments and an SRT file."""

    node_type = "JianyingMerge"

    def _define(self):
        self.inputs = {
            "segments_json": PortSpec(name="segments_json", port_type=PortType.FILE_PATH),
            "rewritten_srt": PortSpec(name="rewritten_srt", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "draft_path": PortSpec(name="draft_path", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "draft_name": ParamSpec(name="draft_name", param_type="string", default=""),
            "draft_folder": ParamSpec(name="draft_folder", param_type="string", default=""),
        }

    async def run(self, inputs, params, work_dir):
        from app.jianying import DEFAULT_DRAFT_FOLDER, create_jianying_merge_draft

        draft = create_jianying_merge_draft(
            inputs["segments_json"],
            inputs["rewritten_srt"],
            draft_folder=params.get("draft_folder") or DEFAULT_DRAFT_FOLDER,
            draft_name=params.get("draft_name") or None,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"draft_path": str(draft)},
        )
