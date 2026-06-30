from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType


DEMUCS_MODELS = ["htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra", "mdx_extra_q"]


class VocalSeparation(Node):
    """Separate vocals and accompaniment from an input video/audio file with Demucs."""

    node_type = "VocalSeparation"

    def _define(self):
        self.inputs = {
            "audio_path": PortSpec(name="audio_path", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "vocals_audio": PortSpec(
                name="vocals_audio",
                port_type=PortType.FILE_PATH,
                description="Separated vocals WAV",
            ),
            "accompaniment_audio": PortSpec(
                name="accompaniment_audio",
                port_type=PortType.FILE_PATH,
                description="Separated accompaniment WAV",
            ),
            "separated_dir": PortSpec(
                name="separated_dir",
                port_type=PortType.FILE_PATH,
                description="Demucs output directory",
            ),
        }
        self.params = {
            "model": ParamSpec(name="model", param_type="select", default="htdemucs", options=DEMUCS_MODELS),
        }

    async def run(self, inputs, params, work_dir):
        from app.audio_util import separate_vocals

        result = separate_vocals(
            inputs["audio_path"],
            output_dir=work_dir / "vocal_separation",
            model=params.get("model", "htdemucs"),
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "vocals_audio": str(result.vocals_path),
                "accompaniment_audio": str(result.accompaniment_path),
                "separated_dir": str(result.output_dir),
            },
        )
