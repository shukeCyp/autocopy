from pathlib import Path

import pytest

from app.audio_util import separate_vocals


def test_separate_vocals_calls_demucs_with_output_md5_path(tmp_path, monkeypatch):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"demo")
    calls = []

    def fake_run(cmd, check):
        calls.append((cmd, check))

    monkeypatch.setattr("app.audio_util.subprocess.run", fake_run)

    output_dir = separate_vocals(video)

    work_dir = Path.cwd() / "output" / "audio" / "fe01ce2a7fbac8fafaed7c982a04e229"
    assert output_dir == work_dir / "separated"
    assert calls == [
        (
            [
                "demucs",
                "--two-stems",
                "vocals",
                "-o",
                str(work_dir / "separated"),
                str(video),
            ],
            True,
        )
    ]


def test_separate_vocals_rejects_missing_video(tmp_path):
    with pytest.raises(FileNotFoundError):
        separate_vocals(tmp_path / "missing.mp4")
