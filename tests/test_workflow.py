from pathlib import Path
from urllib.error import URLError

from app.settings import DEFAULT_SETTINGS
from app.workflow import HotCopyInputs, compose_video, generate_minimax_audio, srt_entries, run_pipeline


def test_srt_entries_preserve_timing(tmp_path):
    srt = tmp_path / "demo.srt"
    srt.write_text(
        "1\n00:00:01,250 --> 00:00:03,000\nfirst line\n\n"
        "2\n00:00:05,000 --> 00:00:06,500\nsecond line\n",
        "utf-8",
    )

    entries = srt_entries(srt)

    assert entries == [
        {"index": 1, "start_ms": 1250, "end_ms": 3000, "text": "first line"},
        {"index": 2, "start_ms": 5000, "end_ms": 6500, "text": "second line"},
    ]


def test_generate_minimax_audio_reuses_existing_file(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"ok")

    result = generate_minimax_audio("text", audio, {"api_key": "", "group_id": ""})

    assert result == audio
    assert audio.read_bytes() == b"ok"


def test_generate_minimax_audio_retries_network_errors(tmp_path, monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data":{"audio":"6f6b"}}'

    def fake_urlopen(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            raise URLError("temporary ssl eof")
        return Response()

    monkeypatch.setattr("app.workflow.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.workflow.time.sleep", lambda seconds: None)

    result = generate_minimax_audio(
        "text",
        tmp_path / "voice.mp3",
        {
            "base_url": "https://api.minimax.chat",
            "group_id": "gid",
            "api_key": "key",
            "model": "speech-02-hd",
            "voice_id": "voice",
            "speed": 1.0,
            "volume": 1.0,
            "pitch": 0,
            "audio_format": "mp3",
        },
    )

    assert result.read_bytes() == b"ok"
    assert len(calls) == 2


def test_compose_video_ducks_original_audio_during_tts(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("app.workflow.subprocess.run", lambda cmd, check: calls.append((cmd, check)))

    compose_video(
        "matched.mp4",
        "tts.m4a",
        tmp_path / "final.mp4",
        {"video_codec": "libx264", "audio_codec": "aac"},
        [{"start_ms": 1000, "end_ms": 2500}],
    )

    cmd = calls[0][0]
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:a:0]volume=enable='between(t,1.000,2.500)':volume=0.2[bg]" in filter_complex
    assert "[bg][1:a:0]amix=inputs=2:duration=first:dropout_transition=0,aformat=channel_layouts=stereo[aout]" in filter_complex
    assert cmd[cmd.index("-map") + 1] == "0:v:0"
    assert "[aout]" in cmd


def test_run_pipeline_uses_settings_and_orders_steps(tmp_path, monkeypatch):
    calls = []

    class FakeTtsResult:
        final_srt_path = tmp_path / "viral.final_tts.srt"

    class FakeRewriter:
        def __init__(self, api_key, model, base_url):
            calls.append(("rewriter", api_key, model, base_url))

        def rewrite_file(self, input_srt, output_srt, target_language, style, max_segment_seconds, max_gap_ms):
            calls.append(("rewrite", input_srt, output_srt, target_language, style, max_segment_seconds, max_gap_ms))
            return output_srt

    def fake_extract_tts_srt(video, **kwargs):
        calls.append(("extract", video, kwargs["gemini_model"], kwargs["base_url"], kwargs["vad_threshold"], kwargs["output_dir"]))
        return FakeTtsResult()

    def fake_match_video(viral, source, output_dir, use_gpu=False):
        calls.append(("match", viral, source, output_dir, use_gpu))
        return {"output_video": str(tmp_path / "matched.mp4")}

    def fake_generate_minimax_audio(text, output_path, settings):
        calls.append(("minimax", text, output_path.name, settings["model"]))
        return output_path

    def fake_compose_timed_audio(entries, audio_paths, output_path):
        calls.append(("timeline", len(entries), [path.name for path in audio_paths], output_path.name))
        return output_path

    def fake_compose_video(video_path, audio_path, output_path, settings, tts_entries):
        calls.append(("compose", video_path, audio_path.name, output_path, settings["audio_codec"], len(tts_entries)))
        return output_path

    def fake_create_jianying_draft(final_video, viral_video):
        calls.append(("draft", final_video, viral_video))
        return tmp_path / "drafts" / "viral"

    monkeypatch.setattr("app.workflow.extract_tts_srt", fake_extract_tts_srt)
    monkeypatch.setattr("app.workflow.GeminiSrtRewriter", FakeRewriter)
    monkeypatch.setattr("app.workflow.match_tuil.match_video", fake_match_video)
    monkeypatch.setattr("app.workflow.generate_minimax_audio", fake_generate_minimax_audio)
    monkeypatch.setattr("app.workflow.compose_timed_audio", fake_compose_timed_audio)
    monkeypatch.setattr("app.workflow.compose_video", fake_compose_video)
    monkeypatch.setattr("app.workflow.create_jianying_draft", fake_create_jianying_draft)
    monkeypatch.setattr(
        "app.workflow.srt_entries",
        lambda path: [
            {"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "one"},
            {"index": 2, "start_ms": 3000, "end_ms": 4000, "text": "two"},
        ],
    )

    settings = DEFAULT_SETTINGS | {
        "paths": DEFAULT_SETTINGS["paths"] | {"output_dir": str(tmp_path)},
        "llm": DEFAULT_SETTINGS["llm"] | {"api_key": "key"},
        "video_match": DEFAULT_SETTINGS["video_match"] | {"gpu_enabled": True},
    }

    result = run_pipeline(HotCopyInputs("viral.mp4", "movie.mp4", tmp_path, "notes"), settings)

    assert result["final_video"] == str(tmp_path / "final.mp4")
    assert result["jianying_draft"] == str(tmp_path / "drafts" / "viral")
    assert [call[0] for call in calls] == ["extract", "rewriter", "rewrite", "match", "minimax", "minimax", "timeline", "compose", "draft"]
    assert calls[0][-1] == tmp_path / "tts"
    assert calls[3][-2:] == (tmp_path / "match", True)
    assert calls[-2][-1] == 2
