from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class VideoMatch(Node):
    """Find matching shots from source movie for each viral video frame."""

    node_type = "VideoMatch"

    def _define(self):
        self.inputs = {
            "viral_video_info": PortSpec(name="viral_video_info", port_type=PortType.VIDEO_INFO),
            "source_video_info": PortSpec(name="source_video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "matched_video": PortSpec(name="matched_video", port_type=PortType.FILE_PATH),
            "segments_json": PortSpec(name="segments_json", port_type=PortType.FILE_PATH),
            "review_html": PortSpec(name="review_html", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "use_gpu": ParamSpec(name="use_gpu", param_type="bool", default=False),
        }

    async def run(self, inputs, params, work_dir):
        from app.copied import match_tuil

        result = match_tuil.match_video(
            inputs["viral_video_info"]["path"],
            inputs["source_video_info"]["path"],
            work_dir,
            use_gpu=params.get("use_gpu", False),
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "matched_video": result["output_video"],
                "segments_json": result["segments"],
                "review_html": result["output_html"],
            },
        )
