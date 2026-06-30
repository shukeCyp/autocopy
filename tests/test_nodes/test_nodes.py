from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.video_input import VideoInput
from app.nodes.video_audio_extract import VideoAudioExtract
from app.nodes.vocal_separation import VocalSeparation
from app.nodes.voice_vad import VoiceVAD
from app.nodes.dominant_speaker import DominantSpeaker
from app.nodes.segment_asr import SegmentASR
from app.nodes.tts_extract import TTSExtract
from app.nodes.srt_rewrite import SRTRewrite
from app.nodes.video_match import VideoMatch
from app.nodes.video_match_vmf import VideoMatchVMF
from app.nodes.tts_generate import TTSGenerate
from app.nodes.video_compose import VideoCompose
from app.nodes.jianying_merge import JianyingMerge
from app.nodes.jianying_export import JianyingExport
from app.pipeline.node import Node
from app.pipeline.types import NodeStatus, PortType
from app.tts_strip import PYANNOTE_EMBEDDING_MODEL


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

    @pytest.mark.asyncio
    async def test_run_blank_path_reports_required_path(self, tmp_path):
        node = VideoInput()
        with pytest.raises(ValueError, match="video path is required"):
            await node.run({}, {"path": ""}, tmp_path)


class TestVideoAudioExtract:
    def test_node_type(self):
        node = VideoAudioExtract()
        assert node.type == "VideoAudioExtract"

    def test_inputs_outputs(self):
        node = VideoAudioExtract()
        assert node.inputs["video_info"].port_type == PortType.VIDEO_INFO
        assert node.outputs["audio_path"].port_type == PortType.FILE_PATH

    def test_params(self):
        node = VideoAudioExtract()
        assert node.params["audio_format"].default == "wav"

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VideoAudioExtract()
        output = tmp_path / "audio.wav"

        with patch("app.audio_util.extract_audio_track", return_value=output) as mock_extract:
            result = await node.run(
                {"video_info": {"path": "/fake/demo.mp4"}},
                {"audio_format": "wav"},
                tmp_path,
            )

        assert result.success
        assert result.outputs["audio_path"] == str(output)
        mock_extract.assert_called_once_with("/fake/demo.mp4", tmp_path / "audio.wav")


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
        assert node.params["min_speech_ms"].default == 10
        assert node.params["min_silence_ms"].default == 50

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
                    "whisper_model": "ggml-large-v3-turbo.bin",
                    "vad_model": "ggml-silero-v6.2.0.bin",
                    "vad_threshold": 0.25,
                    "min_speech_ms": 10,
                    "min_silence_ms": 50,
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
        assert mock_extract.call_args.kwargs["min_speech_ms"] == 10
        assert mock_extract.call_args.kwargs["min_silence_ms"] == 50


class TestVocalSeparation:
    def test_node_type(self):
        node = VocalSeparation()
        assert node.type == "VocalSeparation"

    def test_params(self):
        node = VocalSeparation()
        assert "model" in node.params
        assert node.params["model"].default == "htdemucs"
        assert "htdemucs_ft" in node.params["model"].options

    def test_inputs(self):
        node = VocalSeparation()
        assert "audio_path" in node.inputs
        assert node.inputs["audio_path"].port_type == PortType.FILE_PATH

    def test_outputs(self):
        node = VocalSeparation()
        assert "vocals_audio" in node.outputs
        assert "accompaniment_audio" in node.outputs
        assert "separated_dir" in node.outputs
        for name in ("vocals_audio", "accompaniment_audio", "separated_dir"):
            assert node.outputs[name].port_type == PortType.FILE_PATH

    def test_registered_for_from_dict(self):
        node = Node.from_dict({
            "id": "vocal_sep",
            "type": "VocalSeparation",
            "label": "人声分离",
            "x": 10,
            "y": 20,
            "status": "idle",
            "inputs": {},
            "outputs": {},
            "params": {},
        })

        assert isinstance(node, VocalSeparation)
        assert node.id == "vocal_sep"

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VocalSeparation()
        mock_result = MagicMock()
        mock_result.output_dir = tmp_path / "vocal_separation"
        mock_result.vocals_path = tmp_path / "vocal_separation" / "htdemucs" / "demo" / "vocals.wav"
        mock_result.accompaniment_path = tmp_path / "vocal_separation" / "htdemucs" / "demo" / "no_vocals.wav"

        with patch("app.audio_util.separate_vocals", return_value=mock_result) as mock_separate:
            result = await node.run(
                {"audio_path": "/fake/demo.wav"},
                {"model": "htdemucs_ft"},
                tmp_path,
            )

        assert result.success
        assert result.outputs["vocals_audio"] == str(mock_result.vocals_path)
        assert result.outputs["accompaniment_audio"] == str(mock_result.accompaniment_path)
        assert result.outputs["separated_dir"] == str(mock_result.output_dir)
        mock_separate.assert_called_once_with(
            "/fake/demo.wav",
            output_dir=tmp_path / "vocal_separation",
            model="htdemucs_ft",
        )


class TestVoiceVAD:
    def test_node_type(self):
        node = VoiceVAD()
        assert node.type == "VoiceVAD"

    def test_params(self):
        node = VoiceVAD()
        assert "vad_model" in node.params
        assert node.params["vad_model"].default == "ggml-silero-v6.2.0.bin"
        assert node.params["vad_model"].required is True
        assert node.params["vad_threshold"].default == 0.25
        assert node.params["min_speech_ms"].default == 10
        assert node.params["min_silence_ms"].default == 50

    def test_validate_reports_missing_model(self):
        node = VoiceVAD(id="vad")

        issues = node.validate(
            {"audio_path": "/tmp/audio.wav"},
            {
                "vad_model": "definitely-missing-vad-model.bin",
                "vad_threshold": 0.25,
                "min_speech_ms": 10,
                "min_silence_ms": 50,
            },
        )

        assert issues[0].code == "missing_model"
        assert issues[0].field == "vad_model"
        assert issues[0].node_id == "vad"

    def test_inputs_outputs(self):
        node = VoiceVAD()
        assert node.inputs["audio_path"].port_type == PortType.FILE_PATH
        assert node.outputs["speech_segments_json"].port_type == PortType.FILE_PATH
        assert node.outputs["speech_segments_dir"].port_type == PortType.FILE_PATH

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VoiceVAD()
        mock_result = MagicMock()
        mock_result.segments_json = tmp_path / "vad" / "segments.json"
        mock_result.segments_dir = tmp_path / "vad"

        with patch("app.tts_strip.split_speech_segments", return_value=mock_result) as mock_split:
            result = await node.run(
                {"audio_path": "/fake/vocals.wav"},
                {
                    "vad_model": "ggml-silero-v6.2.0.bin",
                    "vad_threshold": 0.25,
                    "min_speech_ms": 10,
                    "min_silence_ms": 50,
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["speech_segments_json"] == str(mock_result.segments_json)
        assert result.outputs["speech_segments_dir"] == str(mock_result.segments_dir)
        mock_split.assert_called_once()
        assert mock_split.call_args.kwargs["output_dir"] == tmp_path / "vad_segments"
        assert mock_split.call_args.kwargs["min_speech_ms"] == 10
        assert mock_split.call_args.kwargs["min_silence_ms"] == 50


class TestDominantSpeaker:
    def test_node_type(self):
        node = DominantSpeaker()
        assert node.type == "DominantSpeaker"

    def test_inputs_outputs(self):
        node = DominantSpeaker()
        assert node.inputs["speech_segments_json"].port_type == PortType.FILE_PATH
        assert node.outputs["dominant_segments_json"].port_type == PortType.FILE_PATH
        assert node.outputs["speaker_report_json"].port_type == PortType.FILE_PATH
        assert "hf_token" in node.params
        assert node.params["pyannote_model"].default == PYANNOTE_EMBEDDING_MODEL

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = DominantSpeaker()
        mock_result = MagicMock()
        mock_result.segments_json = tmp_path / "dominant_segments.json"
        mock_result.report_json = tmp_path / "speaker_report.json"
        mock_result.speaker_id = 1

        with patch("app.tts_strip.select_dominant_speaker", return_value=mock_result) as mock_select:
            result = await node.run(
                {"speech_segments_json": "/fake/segments.json"},
                {
                    "similarity_threshold": 0.82,
                    "hf_token": "hf_test",
                    "pyannote_model": "pyannote/custom-embedding",
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["dominant_segments_json"] == str(mock_result.segments_json)
        assert result.outputs["speaker_report_json"] == str(mock_result.report_json)
        assert result.outputs["dominant_speaker_id"] == 1
        mock_select.assert_called_once_with(
            "/fake/segments.json",
            output_json=tmp_path / "dominant_segments.json",
            report_json=tmp_path / "speaker_report.json",
            similarity_threshold=0.82,
            hf_token="hf_test",
            model_source="pyannote/custom-embedding",
        )


class TestSegmentASR:
    def test_node_type(self):
        node = SegmentASR()
        assert node.type == "SegmentASR"

    def test_params(self):
        node = SegmentASR()
        assert node.params["whisper_model"].default == "ggml-large-v3-turbo.bin"
        assert node.params["whisper_model"].required is True
        assert node.params["asr_language"].default == "en"
        assert node.params["speaker_filter"].default is True
        assert node.params["speaker_threshold"].default == 0.3
        assert node.params["timing_offset_ms"].default == 0

    def test_validate_reports_missing_whisper_model(self):
        node = SegmentASR(id="asr")

        issues = node.validate(
            {"segments_json": "/tmp/segments.json"},
            {
                "whisper_model": "definitely-missing-whisper-model.bin",
                "asr_language": "en",
                "prompt": "",
                "speaker_filter": True,
                "speaker_threshold": 0.3,
                "timing_offset_ms": 0,
            },
        )

        assert issues[0].code == "missing_model"
        assert issues[0].field == "whisper_model"
        assert issues[0].node_id == "asr"

    def test_inputs_outputs(self):
        node = SegmentASR()
        assert node.inputs["segments_json"].port_type == PortType.FILE_PATH
        assert "srt_content" in node.outputs
        assert node.outputs["srt_content"].port_type == PortType.SRT_CONTENT

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = SegmentASR()
        mock_result = MagicMock()
        mock_result.srt_path = tmp_path / "tts_script.srt"
        mock_result.srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

        with patch("app.tts_strip.transcribe_segments_to_srt", return_value=mock_result) as mock_asr:
            result = await node.run(
                {"segments_json": "/fake/dominant_segments.json"},
                {
                    "whisper_model": "ggml-large-v3-turbo.bin",
                    "asr_language": "en",
                    "prompt": "recap",
                    "speaker_filter": True,
                    "speaker_threshold": 0.3,
                    "timing_offset_ms": 820,
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["srt_content"] == "1\n00:00:01,000 --> 00:00:02,000\nHello\n"
        mock_asr.assert_called_once()
        assert mock_asr.call_args.kwargs["output_srt"] == tmp_path / "tts_script.srt"
        assert mock_asr.call_args.kwargs["speaker_filter"] is True
        assert mock_asr.call_args.kwargs["speaker_threshold"] == 0.3
        assert mock_asr.call_args.kwargs["timing_offset_ms"] == 820


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
        assert "srt_content" in node.inputs
        assert node.inputs["srt_content"].port_type == PortType.SRT_CONTENT

    def test_outputs(self):
        node = SRTRewrite()
        assert "rewritten_srt" in node.outputs
        assert node.outputs["rewritten_srt"].port_type == PortType.FILE_PATH

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = SRTRewrite()
        input_srt = "1\n00:00:01,000 --> 00:00:04,000\nTest subtitle\n"

        mock_rewriter = MagicMock()
        with patch("app.copied.srt_llm_rewriter.GeminiSrtRewriter", return_value=mock_rewriter) as mock_cls:
            result = await node.run(
                {"srt_content": input_srt},
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
        written_input_path = mock_rewriter.rewrite_file.call_args.args[0]
        assert written_input_path.read_text(encoding="utf-8") == input_srt


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
        assert "segments_json" in node.outputs
        assert set(node.outputs) == {"segments_json"}

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VideoMatch()
        with patch("app.copied.match_tuil.match_frames", return_value={
            "segments": "/fake/segments.json",
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
        assert result.outputs == {"segments_json": "/fake/segments.json"}
        mock_match.assert_called_once_with(
            "/fake/viral.mp4",
            "/fake/source.mp4",
            tmp_path,
            use_gpu=True,
        )


class TestVideoMatchVMF:
    def test_node_type(self):
        node = VideoMatchVMF()
        assert node.type == "VideoMatchVMF"

    def test_params(self):
        node = VideoMatchVMF()
        assert node.params["vmf_bin"].default == "vmf"
        assert node.params["fps"].default == 2.0
        assert node.params["model"].default == "dinov2_vits14"
        assert node.params["model"].options == ["dinov2_vits14", "dinov2_vitb14"]
        assert node.params["device"].default == "auto"
        assert node.params["keyframes_only"].default is False

    def test_inputs(self):
        node = VideoMatchVMF()
        assert "viral_video_info" in node.inputs
        assert "source_video_info" in node.inputs

    def test_outputs(self):
        node = VideoMatchVMF()
        assert "segments_json" in node.outputs
        assert "vmf_results_json" in node.outputs
        assert set(node.outputs) == {"segments_json", "vmf_results_json"}

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = VideoMatchVMF()
        with patch("app.vmf_match.run_vmf_match", return_value={
            "segments_json": "/fake/vmf-segments.json",
            "vmf_results_json": "/fake/vmf-results.json",
        }) as mock_match:
            result = await node.run(
                {
                    "viral_video_info": {"path": "/fake/viral.mp4", "fps": 30.0},
                    "source_video_info": {"path": "/fake/source.mp4", "fps": 24.0},
                },
                {
                    "vmf_bin": "vmf",
                    "fps": 2.0,
                    "model": "dinov2_vitb14",
                    "device": "cpu",
                    "no_mirror": True,
                    "keyframes_only": True,
                    "no_cropdetect": True,
                    "legacy_ransac": True,
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["segments_json"] == "/fake/vmf-segments.json"
        assert result.outputs["vmf_results_json"] == "/fake/vmf-results.json"
        mock_match.assert_called_once_with(
            "/fake/viral.mp4",
            "/fake/source.mp4",
            tmp_path,
            viral_video_info={"path": "/fake/viral.mp4", "fps": 30.0},
            source_video_info={"path": "/fake/source.mp4", "fps": 24.0},
            vmf_bin="vmf",
            fps=2.0,
            model="dinov2_vitb14",
            device="cpu",
            no_mirror=True,
            keyframes_only=True,
            no_cropdetect=True,
            legacy_ransac=True,
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


class TestJianyingMerge:
    def test_node_type(self):
        node = JianyingMerge()
        assert node.type == "JianyingMerge"

    def test_inputs_outputs(self):
        node = JianyingMerge()
        assert node.inputs["segments_json"].port_type == PortType.FILE_PATH
        assert node.inputs["rewritten_srt"].port_type == PortType.FILE_PATH
        assert node.outputs["draft_path"].port_type == PortType.FILE_PATH

    def test_params(self):
        node = JianyingMerge()
        assert node.params["draft_name"].default == ""
        assert node.params["draft_folder"].default == ""

    @pytest.mark.asyncio
    async def test_run(self, tmp_path):
        node = JianyingMerge()
        draft = tmp_path / "draft"

        with patch("app.jianying.create_jianying_merge_draft", return_value=draft) as mock_merge:
            result = await node.run(
                {
                    "segments_json": "/fake/segments.json",
                    "rewritten_srt": "/fake/rewritten.srt",
                },
                {
                    "draft_name": "demo",
                    "draft_folder": "/fake/drafts",
                },
                tmp_path,
            )

        assert result.success
        assert result.outputs["draft_path"] == str(draft)
        mock_merge.assert_called_once_with(
            "/fake/segments.json",
            "/fake/rewritten.srt",
            draft_folder="/fake/drafts",
            draft_name="demo",
        )
