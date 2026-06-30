from pathlib import Path
import subprocess
import sys

import pytest

from app import audio_util
from app.audio_util import extract_audio_track, separate_vocals


def test_extract_audio_track_calls_ffmpeg_and_returns_output_path(tmp_path, monkeypatch):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "audio.wav"
    calls = []

    def fake_run(cmd, check, stdout, stderr):
        calls.append((cmd, check, stdout, stderr))
        output.write_bytes(b"audio")

    monkeypatch.setattr(audio_util.subprocess, "run", fake_run)

    result = extract_audio_track(video, output)

    assert result == output
    assert calls == [
        (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video),
                "-vn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output),
            ],
            True,
            subprocess.PIPE,
            subprocess.PIPE,
        )
    ]


def test_separate_vocals_calls_demucs_with_model_and_returns_stems(tmp_path, monkeypatch):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"demo")
    calls = []

    def fake_run(cmd, check, stdout, stderr, env=None):
        calls.append((cmd, check, stdout, stderr, env))
        output_dir = Path(cmd[cmd.index("-o") + 1])
        model = cmd[cmd.index("-n") + 1]
        stem_dir = output_dir / model / video.stem
        stem_dir.mkdir(parents=True)
        (stem_dir / "vocals.wav").write_bytes(b"vocals")
        (stem_dir / "no_vocals.wav").write_bytes(b"music")

    monkeypatch.setattr("app.audio_util.subprocess.run", fake_run)
    monkeypatch.setattr("app.audio_util.shutil.which", lambda name: "demucs")

    output_dir = tmp_path / "demucs_output"
    result = separate_vocals(video, output_dir=output_dir, model="htdemucs_ft")

    assert result.output_dir == output_dir
    assert result.vocals_path == output_dir / "htdemucs_ft" / "demo" / "vocals.wav"
    assert result.accompaniment_path == output_dir / "htdemucs_ft" / "demo" / "no_vocals.wav"
    assert calls[0][:4] == (
        [
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            "htdemucs_ft",
            "-o",
            str(output_dir),
            str(video),
        ],
        True,
        subprocess.PIPE,
        subprocess.PIPE,
    )
    assert calls[0][4]["TORCH_HOME"] == str((Path("model") / "torch").resolve())


def test_separate_vocals_falls_back_to_python_module_when_demucs_not_on_path(tmp_path, monkeypatch):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"demo")
    calls = []

    def fake_run(cmd, check, stdout, stderr, env=None):
        calls.append((cmd, env))
        output_dir = Path(cmd[cmd.index("-o") + 1])
        model = cmd[cmd.index("-n") + 1]
        stem_dir = output_dir / model / video.stem
        stem_dir.mkdir(parents=True)
        (stem_dir / "vocals.wav").write_bytes(b"vocals")
        (stem_dir / "no_vocals.wav").write_bytes(b"music")

    monkeypatch.setattr(audio_util.shutil, "which", lambda name: None)
    monkeypatch.setattr(audio_util.subprocess, "run", fake_run)

    separate_vocals(video, output_dir=tmp_path / "demucs_output")

    assert calls[0][0][:3] == [sys.executable, "-m", "demucs.separate"]
    assert calls[0][1]["TORCH_HOME"] == str((Path("model") / "torch").resolve())


def test_separate_vocals_rejects_missing_video(tmp_path):
    with pytest.raises(FileNotFoundError):
        separate_vocals(tmp_path / "missing.mp4")
