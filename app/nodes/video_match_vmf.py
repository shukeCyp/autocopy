from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType
from app.vmf_match import DEFAULT_VMF_MODEL, VMF_MODELS


class VideoMatchVMF(Node):
    """Match source footage to the viral video using video-match-finder."""

    node_type = "VideoMatchVMF"

    def _define(self):
        self.inputs = {
            "viral_video_info": PortSpec(name="viral_video_info", port_type=PortType.VIDEO_INFO),
            "source_video_info": PortSpec(name="source_video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "segments_json": PortSpec(name="segments_json", port_type=PortType.FILE_PATH),
            "vmf_results_json": PortSpec(name="vmf_results_json", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "vmf_bin": ParamSpec(name="vmf_bin", param_type="string", default="vmf", required=True),
            "fps": ParamSpec(name="fps", param_type="float", default=2.0),
            "model": ParamSpec(
                name="model",
                param_type="select",
                default=DEFAULT_VMF_MODEL,
                options=list(VMF_MODELS),
            ),
            "device": ParamSpec(
                name="device",
                param_type="select",
                default="auto",
                options=["auto", "cpu", "cuda"],
            ),
            "no_mirror": ParamSpec(name="no_mirror", param_type="bool", default=False),
            "keyframes_only": ParamSpec(name="keyframes_only", param_type="bool", default=False),
            "no_cropdetect": ParamSpec(name="no_cropdetect", param_type="bool", default=False),
            "legacy_ransac": ParamSpec(name="legacy_ransac", param_type="bool", default=False),
        }

    async def run(self, inputs, params, work_dir):
        from app.vmf_match import run_vmf_match

        result = run_vmf_match(
            inputs["viral_video_info"]["path"],
            inputs["source_video_info"]["path"],
            work_dir,
            viral_video_info=inputs["viral_video_info"],
            source_video_info=inputs["source_video_info"],
            vmf_bin=params.get("vmf_bin", "vmf"),
            fps=params.get("fps", 2.0),
            model=params.get("model", DEFAULT_VMF_MODEL),
            device=params.get("device", "auto"),
            no_mirror=params.get("no_mirror", False),
            keyframes_only=params.get("keyframes_only", False),
            no_cropdetect=params.get("no_cropdetect", False),
            legacy_ransac=params.get("legacy_ransac", False),
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs=result,
        )
