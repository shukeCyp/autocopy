from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec
from app.pipeline.validation import PathExistsRule


class VideoInput(Node):
    """Input node that reads video metadata via ffprobe."""

    node_type = "VideoInput"

    def _define(self):
        self.inputs = {}
        self.outputs = {
            "video_info": PortSpec(name="video_info", port_type=PortType.VIDEO_INFO),
        }
        self.params = {
            "path": ParamSpec(
                name="path",
                param_type="string",
                default="",
                description="Video file path",
                required=True,
            ),
        }

    def custom_validation_rules(self):
        return [PathExistsRule(field="path", source="param", code="missing_file", label="video")]

    async def run(self, inputs, params, work_dir):
        raw_path = str(params.get("path", "")).strip()
        if not raw_path:
            raise ValueError("video path is required")

        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"video not found: {path}")

        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration,avg_frame_rate",
                "-of", "json", str(path),
            ],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stream = json.loads(result.stdout)["streams"][0]
        fps_str = stream.get("avg_frame_rate", "0/1")
        duration_val = stream.get("duration", 0) or 0
        info = {
            "path": str(path.resolve()),
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "duration": float(duration_val),
            "fps": float(Fraction(fps_str)),
        }
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"video_info": info},
        )
