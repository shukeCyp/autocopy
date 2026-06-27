from __future__ import annotations

import json
from pathlib import Path

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class VideoCompose(Node):
    """Compose final video with matched video + TTS audio mixed in."""

    node_type = "VideoCompose"

    def _define(self):
        self.inputs = {
            "matched_video": PortSpec(name="matched_video", port_type=PortType.FILE_PATH),
            "timeline_audio": PortSpec(name="timeline_audio", port_type=PortType.FILE_PATH),
            "tts_entries_json": PortSpec(name="tts_entries_json", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "final_video": PortSpec(name="final_video", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "video_codec": ParamSpec(name="video_codec", param_type="string", default="libx264"),
            "audio_codec": ParamSpec(name="audio_codec", param_type="string", default="aac"),
        }

    async def run(self, inputs, params, work_dir):
        from app.workflow import compose_video

        tts_entries = json.loads(Path(inputs["tts_entries_json"]).read_text())
        output = work_dir / "final.mp4"
        compose_video(
            inputs["matched_video"],
            inputs["timeline_audio"],
            output,
            {
                "video_codec": params.get("video_codec", "libx264"),
                "audio_codec": params.get("audio_codec", "aac"),
            },
            tts_entries,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"final_video": str(output)},
        )
