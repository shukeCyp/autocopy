from __future__ import annotations

from app.nodes.tts_extract import resolve_model_path
from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType
from app.pipeline.validation import PathExistsRule


class VoiceVAD(Node):
    """Split vocals into speech segments with whisper.cpp VAD."""

    node_type = "VoiceVAD"

    def _define(self):
        self.inputs = {
            "audio_path": PortSpec(name="audio_path", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "speech_segments_json": PortSpec(
                name="speech_segments_json",
                port_type=PortType.FILE_PATH,
                description="VAD speech segments JSON",
            ),
            "speech_segments_dir": PortSpec(
                name="speech_segments_dir",
                port_type=PortType.FILE_PATH,
                description="Directory containing split speech WAV files",
            ),
        }
        self.params = {
            "vad_model": ParamSpec(
                name="vad_model",
                param_type="string",
                default="ggml-silero-v6.2.0.bin",
                required=True,
            ),
            "vad_threshold": ParamSpec(name="vad_threshold", param_type="float", default=0.25),
            "min_speech_ms": ParamSpec(name="min_speech_ms", param_type="int", default=10),
            "min_silence_ms": ParamSpec(name="min_silence_ms", param_type="int", default=50),
        }

    def custom_validation_rules(self):
        return [
            PathExistsRule(
                field="vad_model",
                source="param",
                code="missing_model",
                label="VAD model",
                resolver=resolve_model_path,
            )
        ]

    async def run(self, inputs, params, work_dir):
        from app.tts_strip import split_speech_segments

        result = split_speech_segments(
            inputs["audio_path"],
            vad_model=resolve_model_path(params["vad_model"]),
            output_dir=work_dir / "vad_segments",
            threshold=params["vad_threshold"],
            min_speech_ms=params["min_speech_ms"],
            min_silence_ms=params["min_silence_ms"],
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "speech_segments_json": str(result.segments_json),
                "speech_segments_dir": str(result.segments_dir),
            },
        )
