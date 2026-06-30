from __future__ import annotations

from pathlib import Path

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec
from app.pipeline.validation import PathExistsRule, RequiredParamOrEnvRule


def resolve_model_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or path.parts[:1] == ("model",):
        return path
    if path.parent != Path("."):
        return path
    return Path("model") / path


class TTSExtract(Node):
    """Extract TTS narration from a viral video using Gemini + Whisper + VAD."""

    node_type = "TTSExtract"

    def _define(self):
        self.inputs = {
            "video_info": PortSpec(name="video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "script_txt": PortSpec(name="script_txt", port_type=PortType.FILE_PATH, description="Gemini transcript text"),
            "full_srt": PortSpec(name="full_srt", port_type=PortType.FILE_PATH, description="Full ASR subtitles"),
            "final_srt": PortSpec(name="final_srt", port_type=PortType.FILE_PATH, description="Filtered TTS subtitles"),
        }
        self.params = {
            "api_key": ParamSpec(name="api_key", param_type="string", default=""),
            "gemini_model": ParamSpec(name="gemini_model", param_type="string", default="gemini-3.5-flash", required=True),
            "base_url": ParamSpec(name="base_url", param_type="string", default="https://yunwu.ai", required=True),
            "whisper_model": ParamSpec(name="whisper_model", param_type="string", default="ggml-large-v3-turbo.bin", required=True),
            "vad_model": ParamSpec(name="vad_model", param_type="string", default="ggml-silero-v6.2.0.bin", required=True),
            "vad_threshold": ParamSpec(name="vad_threshold", param_type="float", default=0.25),
            "min_speech_ms": ParamSpec(name="min_speech_ms", param_type="int", default=10),
            "min_silence_ms": ParamSpec(name="min_silence_ms", param_type="int", default=50),
            "min_word_overlap": ParamSpec(name="min_word_overlap", param_type="float", default=0.85),
            "refresh_gemini": ParamSpec(name="refresh_gemini", param_type="bool", default=False),
        }

    def custom_validation_rules(self):
        return [
            RequiredParamOrEnvRule(param_name="api_key", env_names=("YUNWU_API_KEY",)),
            PathExistsRule(
                field="whisper_model",
                source="param",
                code="missing_model",
                label="Whisper model",
                resolver=resolve_model_path,
            ),
            PathExistsRule(
                field="vad_model",
                source="param",
                code="missing_model",
                label="VAD model",
                resolver=resolve_model_path,
            ),
        ]

    async def run(self, inputs, params, work_dir):
        from app.copied.tts_srt_extractor import extract_tts_srt

        video_path = inputs["video_info"]["path"]
        result = extract_tts_srt(
            video_path,
            api_key=params["api_key"],
            gemini_model=params["gemini_model"],
            base_url=params["base_url"],
            whisper_model=resolve_model_path(params["whisper_model"]),
            vad_model=resolve_model_path(params["vad_model"]),
            vad_threshold=params["vad_threshold"],
            min_speech_ms=params["min_speech_ms"],
            min_silence_ms=params["min_silence_ms"],
            min_word_overlap=params["min_word_overlap"],
            refresh_gemini=params["refresh_gemini"],
            output_dir=work_dir,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "script_txt": str(result.script_path),
                "full_srt": str(result.full_asr_srt_path),
                "final_srt": str(result.final_srt_path),
            },
        )
