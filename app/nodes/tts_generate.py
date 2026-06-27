from __future__ import annotations

import json
from pathlib import Path

from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class TTSGenerate(Node):
    """Generate TTS audio segments via Minimax API and compose into timeline."""

    node_type = "TTSGenerate"

    def _define(self):
        self.inputs = {
            "rewritten_srt": PortSpec(name="rewritten_srt", port_type=PortType.FILE_PATH),
        }
        self.outputs = {
            "timeline_audio": PortSpec(name="timeline_audio", port_type=PortType.FILE_PATH),
            "entries_json": PortSpec(name="entries_json", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "api_key": ParamSpec(name="api_key", param_type="string", default=""),
            "group_id": ParamSpec(name="group_id", param_type="string", default=""),
            "base_url": ParamSpec(name="base_url", param_type="string", default="https://api.minimax.chat"),
            "model": ParamSpec(name="model", param_type="string", default="speech-02-hd"),
            "voice_id": ParamSpec(name="voice_id", param_type="string", default=""),
            "speed": ParamSpec(name="speed", param_type="float", default=1.0),
            "volume": ParamSpec(name="volume", param_type="float", default=1.0),
            "pitch": ParamSpec(name="pitch", param_type="int", default=0),
            "audio_format": ParamSpec(name="audio_format", param_type="string", default="mp3"),
        }

    async def run(self, inputs, params, work_dir):
        from app.workflow import srt_entries, generate_minimax_audio, compose_timed_audio

        entries = srt_entries(inputs["rewritten_srt"])
        segment_dir = work_dir / "audio_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        minimax_settings = {
            "api_key": params["api_key"],
            "group_id": params["group_id"],
            "base_url": params["base_url"],
            "model": params["model"],
            "voice_id": params["voice_id"],
            "speed": params["speed"],
            "volume": params["volume"],
            "pitch": params["pitch"],
            "audio_format": params["audio_format"],
        }

        audio_paths = []
        for entry in entries:
            out_path = segment_dir / f"{entry['index']:04d}.{params['audio_format']}"
            audio_path = generate_minimax_audio(entry["text"], out_path, minimax_settings)
            audio_paths.append(audio_path)

        timeline = compose_timed_audio(entries, audio_paths, work_dir / "voice_timeline.m4a")

        # Write entries for downstream use
        entries_path = work_dir / "tts_entries.json"
        entries_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False))

        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "timeline_audio": str(timeline),
                "entries_json": str(entries_path),
            },
        )
