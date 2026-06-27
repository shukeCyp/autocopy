from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.video_input import VideoInput
from app.nodes.tts_extract import TTSExtract
from app.nodes.srt_rewrite import SRTRewrite
from app.nodes.video_match import VideoMatch
from app.nodes.tts_generate import TTSGenerate
from app.nodes.video_compose import VideoCompose
from app.nodes.jianying_export import JianyingExport
from app.pipeline.types import NodeStatus, PortType


class TestVideoInput:
    def test_node_type(self):
        node = VideoInput()
        assert node.type == "VideoInput"

    def test_params(self):
        node = VideoInput()
        assert "path" in node.params
        assert node.params["path"].param_type == "string"

    def test_inputs(self):
        node = VideoInput()
        assert node.inputs == {}

    def test_outputs(self):
        node = VideoInput()
        assert "video_info" in node.outputs
        assert node.outputs["video_info"].port_type == PortType.VIDEO_INFO

    @pytest.mark.asyncio
    async def test_run_missing_file(self, tmp_path):
        node = VideoInput()
        with pytest.raises(FileNotFoundError, match="video not found"):
            await node.run({}, {"path": "/nonexistent/video.mp4"}, tmp_path)


class TestTTSExtract:
    def test_node_type(self):
        node = TTSExtract()
        assert node.type == "TTSExtract"

    def test_params(self):
        node = TTSExtract()
        assert "api_key" in node.params
        assert "gemini_model" in node.params
        assert "whisper_model" in node.params
        assert "vad_model" in node.params
        assert node.params["vad_threshold"].default == 0.25

    def test_inputs(self):
        node = TTSExtract()
        assert "video_info" in node.inputs
        assert node.inputs["video_info"].port_type == PortType.VIDEO_INFO

    def test_outputs(self):
        node = TTSExtract()
        assert "script_txt" in node.outputs
        assert "full_srt" in node.outputs
        assert "final_srt" in node.outputs
        for name in ("script_txt", "full_srt", "final_srt"):
            assert node.outputs[name].port_type == PortType.FILE_PATH

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = TTSExtract()
        mock_result = MagicMock()
        mock_result.script_path = tmp_path / "script.txt"
        mock_result.full_asr_srt_path = tmp_path / "full.srt"
        mock_result.final_srt_path = tmp_path / "final.srt"
        for p in [mock_result.script_path, mock_result.full_asr_srt_path, mock_result.final_srt_path]:
            p.write_text("test")

        with patch("app.copied.tts_srt_extractor.extract_tts_srt", return_value=mock_result) as mock_extract:
            result = await node.run(
                {"video_info": {"path": "/fake/video.mp4"}},
                {
                    "api_key": "test-key",
                    "gemini_model": "gemini-3.5-flash",
                    "base_url": "https://yunwu.ai",
                    "whisper_model": ".model/ggml-large-v3-turbo.bin",
                    "vad_model": ".model/ggml-silero-v6.2.0.bin",
                    "vad_threshold": 0.25,
                    "min_speech_ms": 30,
                    "min_silence_ms": 250,
                    "min_word_overlap": 0.85,
                    "refresh_gemini": False,
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["script_txt"] == str(mock_result.script_path)
        assert result.outputs["full_srt"] == str(mock_result.full_asr_srt_path)
        assert result.outputs["final_srt"] == str(mock_result.final_srt_path)
        mock_extract.assert_called_once()


class TestSRTRewrite:
    def test_node_type(self):
        node = SRTRewrite()
        assert node.type == "SRTRewrite"

    def test_params(self):
        node = SRTRewrite()
        assert "api_key" in node.params
        assert "target_language" in node.params
        assert node.params["target_language"].default == "Chinese"
        assert node.params["max_segment_seconds"].default == 30

    def test_inputs(self):
        node = SRTRewrite()
        assert "srt_path" in node.inputs
        assert node.inputs["srt_path"].port_type == PortType.FILE_PATH

    def test_outputs(self):
        node = SRTRewrite()
        assert "rewritten_srt" in node.outputs
        assert node.outputs["rewritten_srt"].port_type == PortType.FILE_PATH

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = SRTRewrite()
        input_srt = tmp_path / "input.srt"
        input_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest subtitle\n")

        mock_rewriter = MagicMock()
        with patch("app.copied.srt_llm_rewriter.GeminiSrtRewriter", return_value=mock_rewriter) as mock_cls:
            result = await node.run(
                {"srt_path": str(input_srt)},
                {
                    "api_key": "test-key",
                    "model": "gemini-3.5-flash",
                    "base_url": "https://yunwu.ai",
                    "target_language": "Chinese",
                    "style": "localized short-video crime recap",
                    "max_segment_seconds": 30,
                    "max_gap_ms": 700,
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["rewritten_srt"].endswith("rewritten.srt")
        mock_cls.assert_called_once_with(api_key="test-key", model="gemini-3.5-flash", base_url="https://yunwu.ai")
        mock_rewriter.rewrite_file.assert_called_once()


class TestVideoMatch:
    def test_node_type(self):
        node = VideoMatch()
        assert node.type == "VideoMatch"

    def test_params(self):
        node = VideoMatch()
        assert "use_gpu" in node.params
        assert node.params["use_gpu"].default is False

    def test_inputs(self):
        node = VideoMatch()
        assert "viral_video_info" in node.inputs
        assert "source_video_info" in node.inputs

    def test_outputs(self):
        node = VideoMatch()
        assert "matched_video" in node.outputs
        assert "segments_json" in node.outputs
        assert "review_html" in node.outputs

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VideoMatch()
        with patch("app.copied.match_tuil.match_video", return_value={
            "output_video": "/fake/output.mp4",
            "segments": "/fake/segments.json",
            "output_html": "/fake/review.html",
        }) as mock_match:
            result = await node.run(
                {
                    "viral_video_info": {"path": "/fake/viral.mp4"},
                    "source_video_info": {"path": "/fake/source.mp4"},
                },
                {"use_gpu": True},
                tmp_path,
            )

        assert result.success
        assert result.outputs["matched_video"] == "/fake/output.mp4"
        assert result.outputs["segments_json"] == "/fake/segments.json"
        assert result.outputs["review_html"] == "/fake/review.html"
        mock_match.assert_called_once_with(
            "/fake/viral.mp4",
            "/fake/source.mp4",
            tmp_path,
            use_gpu=True,
        )


class TestTTSGenerate:
    def test_node_type(self):
        node = TTSGenerate()
        assert node.type == "TTSGenerate"

    def test_params(self):
        node = TTSGenerate()
        assert "api_key" in node.params
        assert "voice_id" in node.params
        assert node.params["speed"].default == 1.0
        assert node.params["volume"].default == 1.0

    def test_inputs(self):
        node = TTSGenerate()
        assert "rewritten_srt" in node.inputs
        assert node.inputs["rewritten_srt"].port_type == PortType.FILE_PATH

    def test_outputs(self):
        node = TTSGenerate()
        assert "timeline_audio" in node.outputs
        assert "entries_json" in node.outputs

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = TTSGenerate()
        rewritten_srt = tmp_path / "rewritten.srt"
        rewritten_srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond line\n"
        )

        with (
            patch("app.workflow.srt_entries") as mock_srt_entries,
            patch("app.workflow.generate_minimax_audio") as mock_gen_audio,
            patch("app.workflow.compose_timed_audio") as mock_compose,
        ):
            mock_srt_entries.return_value = [
                {"index": 1, "start_ms": 1000, "end_ms": 4000, "text": "Hello world"},
                {"index": 2, "start_ms": 5000, "end_ms": 8000, "text": "Second line"},
            ]
            mock_gen_audio.side_effect = lambda text, out_path, settings: out_path
            mock_compose.return_value = tmp_path / "voice_timeline.m4a"

            result = await node.run(
                {"rewritten_srt": str(rewritten_srt)},
                {
                    "api_key": "minimax-key",
                    "group_id": "test-group",
                    "base_url": "https://api.minimax.chat",
                    "model": "speech-02-hd",
                    "voice_id": "test-voice",
                    "speed": 1.0,
                    "volume": 1.0,
                    "pitch": 0,
                    "audio_format": "mp3",
                },
                tmp_path,
            )

        assert result.success
        assert str(result.outputs["timeline_audio"]).endswith("voice_timeline.m4a")
        assert str(result.outputs["entries_json"]).endswith("tts_entries.json")
        assert mock_srt_entries.call_count == 1
        assert mock_gen_audio.call_count == 2
        mock_compose.assert_called_once()

        # Verify tts_entries.json was written
        entries_path = Path(result.outputs["entries_json"])
        assert entries_path.exists()


class TestVideoCompose:
    def test_node_type(self):
        node = VideoCompose()
        assert node.type == "VideoCompose"

    def test_params(self):
        node = VideoCompose()
        assert "video_codec" in node.params
        assert node.params["video_codec"].default == "libx264"
        assert "audio_codec" in node.params
        assert node.params["audio_codec"].default == "aac"

    def test_inputs(self):
        node = VideoCompose()
        assert "matched_video" in node.inputs
        assert "timeline_audio" in node.inputs
        assert "tts_entries_json" in node.inputs

    def test_outputs(self):
        node = VideoCompose()
        assert "final_video" in node.outputs
        assert node.outputs["final_video"].port_type == PortType.FILE_PATH

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VideoCompose()
        entries_file = tmp_path / "tts_entries.json"
        entries_file.write_text(
            json.dumps([
                {"index": 1, "start_ms": 1000, "end_ms": 4000, "text": "Hello"},
            ])
        )

        with patch("app.workflow.compose_video") as mock_compose:
            mock_compose.return_value = tmp_path / "final.mp4"
            result = await node.run(
                {
                    "matched_video": "/fake/matched.mp4",
                    "timeline_audio": "/fake/timeline.m4a",
                    "tts_entries_json": str(entries_file),
                },
                {
                    "video_codec": "libx264",
                    "audio_codec": "aac",
                },
                tmp_path,
            )

        assert result.success
        assert str(result.outputs["final_video"]).endswith("final.mp4")
        mock_compose.assert_called_once()

        # Verify tts_entries were loaded from the JSON file
        _call_args = mock_compose.call_args[0]
        assert _call_args[3]["video_codec"] == "libx264"


class TestJianyingExport:
    def test_node_type(self):
        node = JianyingExport()
        assert node.type == "JianyingExport"

    def test_params(self):
        node = JianyingExport()
        assert node.params == {}

    def test_inputs(self):
        node = JianyingExport()
        assert "final_video" in node.inputs
        assert "viral_video_info" in node.inputs

    def test_outputs(self):
        node = JianyingExport()
        assert "draft_path" in node.outputs

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = JianyingExport()
        with patch("app.jianying.create_jianying_draft") as mock_draft:
            mock_draft.return_value = Path("/fake/draft")
            result = await node.run(
                {
                    "final_video": "/fake/final.mp4",
                    "viral_video_info": {"path": "/fake/viral.mp4"},
                },
                {},
                tmp_path,
            )

        assert result.success
        assert result.outputs["draft_path"] == "/fake/draft"
        mock_draft.assert_called_once_with("/fake/final.mp4", "/fake/viral.mp4")
