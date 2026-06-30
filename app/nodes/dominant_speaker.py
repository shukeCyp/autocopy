from __future__ import annotations

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, ParamSpec, PortSpec, PortType
from app.tts_strip import PYANNOTE_EMBEDDING_MODEL


class DominantSpeaker(Node):
    """Cluster speech segments by voice fingerprint and keep the most-spoken speaker."""

    node_type = "DominantSpeaker"

    def _define(self):
        self.inputs = {
            "speech_segments_json": PortSpec(name="speech_segments_json", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "dominant_segments_json": PortSpec(
                name="dominant_segments_json",
                port_type=PortType.FILE_PATH,
                description="Segments belonging to the dominant speaker",
            ),
            "speaker_report_json": PortSpec(
                name="speaker_report_json",
                port_type=PortType.FILE_PATH,
                description="Speaker clustering report",
            ),
            "dominant_speaker_id": PortSpec(
                name="dominant_speaker_id",
                port_type=PortType.JSON_DATA,
                description="Selected speaker cluster id",
            ),
        }
        self.params = {
            "similarity_threshold": ParamSpec(name="similarity_threshold", param_type="float", default=0.82),
            "pyannote_model": ParamSpec(
                name="pyannote_model",
                param_type="string",
                default=PYANNOTE_EMBEDDING_MODEL,
                required=True,
            ),
            "hf_token": ParamSpec(name="hf_token", param_type="string", default=""),
        }

    async def run(self, inputs, params, work_dir):
        from app.tts_strip import select_dominant_speaker

        model_source = str(params.get("pyannote_model") or PYANNOTE_EMBEDDING_MODEL).strip()
        result = select_dominant_speaker(
            inputs["speech_segments_json"],
            output_json=work_dir / "dominant_segments.json",
            report_json=work_dir / "speaker_report.json",
            similarity_threshold=params.get("similarity_threshold", 0.82),
            hf_token=params.get("hf_token", ""),
            model_source=model_source or PYANNOTE_EMBEDDING_MODEL,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "dominant_segments_json": str(result.segments_json),
                "speaker_report_json": str(result.report_json),
                "dominant_speaker_id": result.speaker_id,
            },
        )
