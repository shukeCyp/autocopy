import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np

from app import tts_strip


def test_split_speech_segments_writes_json_and_extracts_wav_segments(tmp_path, monkeypatch):
    audio = tmp_path / "vocals.wav"
    audio.write_bytes(b"audio")
    vad_model = tmp_path / "vad.bin"
    vad_model.write_bytes(b"model")
    calls = []

    monkeypatch.setattr(tts_strip, "vad_segments", lambda *args: [(1.0, 2.25), (3.0, 4.0)])

    def fake_run(cmd, quiet=False):
        calls.append((cmd, quiet))
        Path(cmd[-1]).write_bytes(b"segment")

    monkeypatch.setattr(tts_strip, "run", fake_run)

    result = tts_strip.split_speech_segments(
        audio,
        vad_model=vad_model,
        output_dir=tmp_path / "vad",
        threshold=0.3,
        min_speech_ms=80,
        min_silence_ms=300,
    )

    assert result.segments_json == tmp_path / "vad" / "segments.json"
    assert len(result.segments) == 2
    assert result.segments[0]["start_ms"] == 1000
    assert result.segments[0]["end_ms"] == 2250
    assert result.segments[0]["audio_path"].endswith("segment_0001.wav")
    assert json.loads(result.segments_json.read_text()) == result.segments
    assert calls[0][0][:8] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        "1.000",
        "-to",
    ]
    assert calls[0][0][-5:] == ["-ar", "16000", "-ac", "1", str(tmp_path / "vad" / "segment_0001.wav")]
    assert calls[0][1] is True


def test_split_speech_segments_defaults_to_short_vad_durations(tmp_path, monkeypatch):
    audio = tmp_path / "vocals.wav"
    audio.write_bytes(b"audio")
    vad_model = tmp_path / "vad.bin"
    vad_model.write_bytes(b"model")
    calls = []

    def fake_vad_segments(audio_path, model_path, threshold, min_speech_ms, min_silence_ms):
        calls.append((audio_path, model_path, threshold, min_speech_ms, min_silence_ms))
        return []

    monkeypatch.setattr(tts_strip, "vad_segments", fake_vad_segments)

    result = tts_strip.split_speech_segments(
        audio,
        vad_model=vad_model,
        output_dir=tmp_path / "vad",
    )

    assert result.segments == []
    assert calls == [(audio, vad_model, 0.25, 10, 50)]


def test_select_dominant_speaker_writes_longest_matching_voice_cluster(tmp_path, monkeypatch):
    segment_paths = []
    for index in range(1, 4):
        path = tmp_path / f"segment_{index:04d}.wav"
        path.write_bytes(b"audio")
        segment_paths.append(path)

    segments = [
        {"index": 1, "start_ms": 0, "end_ms": 1000, "duration_ms": 1000, "audio_path": str(segment_paths[0])},
        {"index": 2, "start_ms": 2000, "end_ms": 4000, "duration_ms": 2000, "audio_path": str(segment_paths[1])},
        {"index": 3, "start_ms": 5000, "end_ms": 7400, "duration_ms": 2400, "audio_path": str(segment_paths[2])},
    ]
    segments_json = tmp_path / "segments.json"
    segments_json.write_text(json.dumps(segments))

    embeddings = {
        segment_paths[0]: np.array([1.0, 0.0]),
        segment_paths[1]: np.array([0.99, 0.01]),
        segment_paths[2]: np.array([0.0, 1.0]),
    }
    monkeypatch.setattr(tts_strip, "voice_embedding", lambda path, **kwargs: embeddings[Path(path)])

    result = tts_strip.select_dominant_speaker(
        segments_json,
        output_json=tmp_path / "dominant.json",
        report_json=tmp_path / "report.json",
        similarity_threshold=0.9,
    )

    assert [segment["index"] for segment in result.segments] == [1, 2]
    assert result.speaker_id == 0
    assert json.loads(result.segments_json.read_text()) == result.segments
    report = json.loads(result.report_json.read_text())
    assert report["dominant_speaker_id"] == 0
    assert report["speakers"][0]["total_duration_ms"] == 3000


def test_voice_embedding_uses_pyannote_embedding_model(tmp_path, monkeypatch):
    audio = tmp_path / "segment.wav"
    audio.write_bytes(b"audio")
    calls = []
    inference_calls = []

    class FakeInference:
        def __call__(self, path):
            calls.append(("infer", path))
            return np.array([[2.0, 0.0]])

    def fake_get_pyannote_inference(model_source=None, hf_token=None, savedir=None):
        inference_calls.append((model_source, hf_token, savedir))
        return FakeInference()

    monkeypatch.setattr(
        tts_strip,
        "_get_pyannote_inference",
        fake_get_pyannote_inference,
    )

    embedding = tts_strip.voice_embedding(audio, hf_token="hf_test")

    assert inference_calls == [(tts_strip.PYANNOTE_EMBEDDING_MODEL, "hf_test", None)]
    assert tts_strip.PYANNOTE_EMBEDDING_MODEL == "pyannote/wespeaker-voxceleb-resnet34-LM"
    assert calls == [("infer", str(audio))]
    assert np.allclose(embedding, np.array([1.0, 0.0]))


def test_pyannote_inference_downloads_model_under_model_dir(monkeypatch):
    calls = []

    class FakeModel:
        @staticmethod
        def from_pretrained(model_source, token=None, cache_dir=None):
            calls.append((model_source, token, cache_dir))
            return object()

    class FakeInference:
        def __init__(self, model, window):
            self.model = model
            self.window = window

    fake_audio_module = types.ModuleType("pyannote.audio")
    fake_audio_module.Model = FakeModel
    fake_audio_module.Inference = FakeInference
    monkeypatch.setitem(sys.modules, "pyannote.audio", fake_audio_module)
    tts_strip._get_pyannote_inference.cache_clear()

    inference = tts_strip._get_pyannote_inference(hf_token="hf_test")

    assert isinstance(inference, FakeInference)
    assert calls == [
        (
            tts_strip.PYANNOTE_EMBEDDING_MODEL,
            "hf_test",
            str((Path("model") / "pyannote").resolve()),
        )
    ]


def test_pyannote_dependency_is_declared():
    import tomllib

    data = tomllib.loads(Path("pyproject.toml").read_text())

    assert "pyannote-audio" in {dependency.split(">=")[0] for dependency in data["project"]["dependencies"]}


def test_transcribe_segments_to_srt_offsets_segment_subtitles(tmp_path, monkeypatch):
    audio_a = tmp_path / "segment_0001.wav"
    audio_b = tmp_path / "segment_0002.wav"
    audio_a.write_bytes(b"a")
    audio_b.write_bytes(b"b")
    segments_json = tmp_path / "dominant.json"
    segments_json.write_text(json.dumps([
        {"index": 1, "start_ms": 1000, "end_ms": 2000, "duration_ms": 1000, "audio_path": str(audio_a)},
        {"index": 2, "start_ms": 3000, "end_ms": 4000, "duration_ms": 1000, "audio_path": str(audio_b)},
    ]))
    calls = []

    def fake_run(cmd, quiet=False):
        calls.append((cmd, quiet))
        out_base = Path(cmd[cmd.index("-of") + 1])
        out_base.with_suffix(".srt").write_text(
            "1\n00:00:00,100 --> 00:00:00,700\nhello\n"
        )

    monkeypatch.setattr(tts_strip, "run", fake_run)

    result = tts_strip.transcribe_segments_to_srt(
        segments_json,
        whisper_model=Path("model/ggml-large-v3-turbo.bin"),
        output_srt=tmp_path / "tts.srt",
        work_dir=tmp_path / "asr",
        language="en",
        prompt="recap",
    )

    assert result.srt_path == tmp_path / "tts.srt"
    assert result.entries == [
        (1100, 1700, "hello"),
        (3100, 3700, "hello"),
    ]
    assert "00:00:01,100 --> 00:00:01,700" in result.srt_path.read_text()
    assert "00:00:03,100 --> 00:00:03,700" in result.srt_path.read_text()
    assert calls[0][0][:6] == ["whisper-cli", "-m", "model/ggml-large-v3-turbo.bin", "-l", "en", "-np"]
    assert calls[0][0][-3:] == ["--prompt", "recap", str(audio_a)]
    assert calls[0][1] is True


def test_transcribe_segments_to_srt_applies_timing_offset(tmp_path, monkeypatch):
    audio = tmp_path / "segment_0001.wav"
    audio.write_bytes(b"audio")
    segments_json = tmp_path / "dominant.json"
    segments_json.write_text(json.dumps([
        {"index": 1, "start_ms": 7780, "end_ms": 10000, "duration_ms": 2220, "audio_path": str(audio)},
    ]))

    def fake_run(cmd, quiet=False):
        out_base = Path(cmd[cmd.index("-of") + 1])
        out_base.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,930\nBarney and Marshall were in a\n"
        )

    monkeypatch.setattr(tts_strip, "run", fake_run)

    result = tts_strip.transcribe_segments_to_srt(
        segments_json,
        whisper_model=Path("model/ggml-large-v3-turbo.bin"),
        output_srt=tmp_path / "tts.srt",
        work_dir=tmp_path / "asr",
        timing_offset_ms=820,
    )

    assert result.entries == [(8600, 10530, "Barney and Marshall were in a")]
    assert "00:00:08,600 --> 00:00:10,530" in result.srt_path.read_text()


def test_transcribe_segments_to_srt_filters_lines_by_dominant_speaker(tmp_path, monkeypatch):
    audio = tmp_path / "segment_0001.wav"
    audio.write_bytes(b"audio")
    segments_json = tmp_path / "dominant.json"
    segments_json.write_text(json.dumps([
        {"index": 1, "start_ms": 5000, "end_ms": 10000, "duration_ms": 5000, "audio_path": str(audio)},
    ]))
    sliced_audio: list[Path] = []

    def fake_run(cmd, quiet=False):
        if cmd[0] == "whisper-cli":
            out_base = Path(cmd[cmd.index("-of") + 1])
            out_base.with_suffix(".srt").write_text(
                "\n".join([
                    "1",
                    "00:00:00,000 --> 00:00:01,000",
                    "narrator one",
                    "",
                    "2",
                    "00:00:01,000 --> 00:00:02,000",
                    "dialogue",
                    "",
                    "3",
                    "00:00:02,000 --> 00:00:03,000",
                    "narrator two",
                    "",
                ])
            )
            return
        sliced_audio.append(Path(cmd[-1]))
        Path(cmd[-1]).write_bytes(b"line")

    def fake_voice_embedding(path, **kwargs):
        name = Path(path).stem
        if name.endswith("0002"):
            return np.array([0.0, 1.0], dtype=np.float32)
        return np.array([1.0, 0.0], dtype=np.float32)

    monkeypatch.setattr(tts_strip, "run", fake_run)
    monkeypatch.setattr(tts_strip, "voice_embedding", fake_voice_embedding)

    result = tts_strip.transcribe_segments_to_srt(
        segments_json,
        whisper_model=Path("model/ggml-large-v3-turbo.bin"),
        output_srt=tmp_path / "tts.srt",
        work_dir=tmp_path / "asr",
        speaker_filter=True,
        speaker_threshold=0.3,
    )

    assert len(sliced_audio) == 3
    assert result.entries == [
        (5000, 6000, "narrator one"),
        (7000, 8000, "narrator two"),
    ]
    srt = result.srt_path.read_text()
    assert "narrator one" in srt
    assert "dialogue" not in srt
    assert "narrator two" in srt
