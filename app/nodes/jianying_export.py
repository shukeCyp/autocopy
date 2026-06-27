from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class JianyingExport(Node):
    """Export final video as a Jianying (CapCut) draft project."""

    node_type = "JianyingExport"

    def _define(self):
        self.inputs = {
            "final_video": PortSpec(name="final_video", port_type=PortType.FILE_PATH),
            "viral_video_info": PortSpec(name="viral_video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "draft_path": PortSpec(name="draft_path", port_type=PortType.FILE_PATH),
        }
        self.params = {}

    async def run(self, inputs, params, work_dir):
        from app.jianying import create_jianying_draft

        draft = create_jianying_draft(
            inputs["final_video"],
            inputs["viral_video_info"]["path"],
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"draft_path": str(draft)},
        )
