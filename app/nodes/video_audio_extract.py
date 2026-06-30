from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType


class VideoAudioExtract(Node):
    """Extract a mono WAV audio track from an input video."""

    node_type = "VideoAudioExtract"

    def _define(self):
        self.inputs = {
            "video_info": PortSpec(name="video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "audio_path": PortSpec(name="audio_path", port_type=PortType.FILE_PATH, description="Extracted audio WAV"),
        }
        self.params = {
            "audio_format": ParamSpec(name="audio_format", param_type="select", default="wav", options=["wav"]),
        }

    async def run(self, inputs, params, work_dir):
        from app.audio_util import extract_audio_track

        audio_format = params.get("audio_format", "wav")
        if audio_format != "wav":
            raise ValueError(f"unsupported audio_format: {audio_format}")

        output = extract_audio_track(inputs["video_info"]["path"], work_dir / "audio.wav")
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"audio_path": str(output)},
        )
