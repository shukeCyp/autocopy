import subprocess
from inspect import signature

import pytest

from app.copied import tts_srt_extractor


def test_run_quiet_preserves_stderr_on_failure(monkeypatch):
    captured_kwargs = {}

    def fake_run(cmd, check, **kwargs):
        captured_kwargs.update(kwargs)
        raise subprocess.CalledProcessError(
            returncode=3,
            cmd=cmd,
            stderr=b"failed to load model\n",
        )

    monkeypatch.setattr(tts_srt_extractor.subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError) as exc:
        tts_srt_extractor.run(["whisper-cli"], quiet=True)

    assert captured_kwargs["stdout"] == subprocess.PIPE
    assert captured_kwargs["stderr"] == subprocess.PIPE
    assert exc.value.stderr == b"failed to load model\n"


def test_tts_extractor_defaults_to_short_vad_durations():
    extract_params = signature(tts_srt_extractor.extract_tts_srt).parameters
    vad_params = signature(tts_srt_extractor.vad_segments).parameters

    assert extract_params["min_speech_ms"].default == 10
    assert extract_params["min_silence_ms"].default == 50
    assert vad_params["min_speech_ms"].default == 10
    assert vad_params["min_silence_ms"].default == 50


def test_vad_segments_uses_min_speech_duration_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, check, capture_output, text):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Speech segment 0: start = 100.00, end = 250.00\n",
            stderr="",
        )

    monkeypatch.setattr(tts_srt_extractor.subprocess, "run", fake_run)

    segments = tts_srt_extractor.vad_segments(
        tmp_path / "audio.wav",
        tmp_path / "vad.bin",
        threshold=0.25,
        min_speech_ms=10,
        min_silence_ms=50,
    )

    assert segments == [(1.0, 2.5)]
    assert "--vad-min-speech-duration-ms" in captured["cmd"]
    assert "-vmsd" not in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--vad-min-speech-duration-ms") + 1] == "10"
