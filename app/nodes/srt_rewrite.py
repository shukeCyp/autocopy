from __future__ import annotations

from pathlib import Path

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class SRTRewrite(Node):
    """Rewrite SRT subtitles into target language using an LLM."""

    node_type = "SRTRewrite"

    def _define(self):
        self.inputs = {
            "srt_path": PortSpec(name="srt_path", port_type=PortType.FILE_PATH, description="Input SRT file path"),
        }
        self.outputs = {
            "rewritten_srt": PortSpec(name="rewritten_srt", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "api_key": ParamSpec(name="api_key", param_type="string", default=""),
            "model": ParamSpec(name="model", param_type="string", default="gemini-3.5-flash"),
            "base_url": ParamSpec(name="base_url", param_type="string", default="https://yunwu.ai"),
            "target_language": ParamSpec(name="target_language", param_type="select", default="Chinese", options=["Chinese", "English"]),
            "style": ParamSpec(name="style", param_type="string", default="localized short-video crime recap"),
            "max_segment_seconds": ParamSpec(name="max_segment_seconds", param_type="int", default=30),
            "max_gap_ms": ParamSpec(name="max_gap_ms", param_type="int", default=700),
        }

    async def run(self, inputs, params, work_dir):
        from app.copied.srt_llm_rewriter import GeminiSrtRewriter

        output_path = work_dir / "rewritten.srt"
        rewriter = GeminiSrtRewriter(
            api_key=params["api_key"],
            model=params["model"],
            base_url=params["base_url"],
        )
        rewriter.rewrite_file(
            inputs["srt_path"],
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
