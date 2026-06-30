from __future__ import annotations

from app.nodes.tts_extract import resolve_model_path
from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType
from app.pipeline.validation import PathExistsRule


class SegmentASR(Node):
    """Transcribe selected speech segments and merge them into a timed SRT."""

    node_type = "SegmentASR"

    def _define(self):
        self.inputs = {
            "segments_json": PortSpec(name="segments_json", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "srt_content": PortSpec(name="srt_content", port_type=PortType.SRT_CONTENT, description="ASR SRT text"),
        }
        self.params = {
            "whisper_model": ParamSpec(
                name="whisper_model",
                param_type="string",
                default="ggml-large-v3-turbo.bin",
                required=True,
            ),
            "asr_language": ParamSpec(
                name="asr_language",
                param_type="select",
                default="en",
                options=["en", "zh", "auto"],
            ),
            "prompt": ParamSpec(name="prompt", param_type="string", default=""),
            "speaker_filter": ParamSpec(name="speaker_filter", param_type="bool", default=True),
            "speaker_threshold": ParamSpec(name="speaker_threshold", param_type="float", default=0.3),
            "timing_offset_ms": ParamSpec(name="timing_offset_ms", param_type="int", default=0),
        }

    def custom_validation_rules(self):
        return [
            PathExistsRule(
                field="whisper_model",
                source="param",
                code="missing_model",
                label="Whisper model",
                resolver=resolve_model_path,
            )
        ]

    async def run(self, inputs, params, work_dir):
        from app.tts_strip import transcribe_segments_to_srt

        result = transcribe_segments_to_srt(
            inputs["segments_json"],
            whisper_model=resolve_model_path(params["whisper_model"]),
            output_srt=work_dir / "tts_script.srt",
            work_dir=work_dir / "segment_asr",
            language=params.get("asr_language", "en"),
            prompt=params.get("prompt", ""),
            speaker_filter=params.get("speaker_filter", True),
            speaker_threshold=params.get("speaker_threshold", 0.3),
            timing_offset_ms=params.get("timing_offset_ms", 0),
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"srt_content": result.srt_path.read_text(encoding="utf-8")},
        )
