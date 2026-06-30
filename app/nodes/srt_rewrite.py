from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec
from app.pipeline.validation import RequiredParamOrEnvRule


class SRTRewrite(Node):
    """Rewrite SRT subtitles into target language using an LLM."""

    node_type = "SRTRewrite"

    def _define(self):
        self.inputs = {
            "srt_content": PortSpec(name="srt_content", port_type=PortType.SRT_CONTENT, description="Input SRT text"),
        }
        self.outputs = {
            "rewritten_srt": PortSpec(name="rewritten_srt", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "api_key": ParamSpec(name="api_key", param_type="string", default=""),
            "model": ParamSpec(name="model", param_type="string", default="gemini-3.5-flash", required=True),
            "base_url": ParamSpec(name="base_url", param_type="string", default="https://yunwu.ai", required=True),
            "target_language": ParamSpec(name="target_language", param_type="select", default="Chinese", options=["Chinese", "English"]),
            "style": ParamSpec(name="style", param_type="string", default="localized short-video crime recap"),
            "max_segment_seconds": ParamSpec(name="max_segment_seconds", param_type="int", default=30),
            "max_gap_ms": ParamSpec(name="max_gap_ms", param_type="int", default=700),
        }

    def custom_validation_rules(self):
        return [RequiredParamOrEnvRule(param_name="api_key", env_names=("YUNWU_API_KEY",))]

    async def run(self, inputs, params, work_dir):
        from app.copied.srt_llm_rewriter import GeminiSrtRewriter

        input_path = work_dir / "input.srt"
        output_path = work_dir / "rewritten.srt"
        input_path.write_text(inputs["srt_content"], encoding="utf-8")
        rewriter = GeminiSrtRewriter(
            api_key=params["api_key"],
            model=params["model"],
            base_url=params["base_url"],
        )
        rewriter.rewrite_file(
            input_path,
            output_path,
            params["target_language"],
            params["style"],
            params["max_segment_seconds"],
            params["max_gap_ms"],
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"rewritten_srt": str(output_path)},
        )
