import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.model_cache import model_cache_env


@dataclass(frozen=True)
class VocalSeparationResult:
    output_dir: Path
    vocals_path: Path
    accompaniment_path: Path


def file_md5(path: str | Path) -> str:
    digest = hashlib.md5()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_audio_track(video_path: str | Path, output_path: str | Path) -> Path:
    video = Path(video_path)
    if not video.is_file():
        raise FileNotFoundError(video)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
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
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not output.is_file():
        raise FileNotFoundError(output)
    return output


def separate_vocals(
    video_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    model: str = "htdemucs",
) -> VocalSeparationResult:
    video = Path(video_path)
    if not video.is_file():
        raise FileNotFoundError(video)

    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else Path.cwd() / "output" / "audio" / file_md5(video) / "separated"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    model_name = model or "htdemucs"

    subprocess.run(
        _demucs_command()
        + [
            "--two-stems",
            "vocals",
            "-n",
            model_name,
            "-o",
            str(target_dir),
            str(video),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=model_cache_env(),
    )
    stem_dir = target_dir / model_name / video.stem
    result = VocalSeparationResult(
        output_dir=target_dir,
        vocals_path=stem_dir / "vocals.wav",
        accompaniment_path=stem_dir / "no_vocals.wav",
    )
    for path in (result.vocals_path, result.accompaniment_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    return result


def _demucs_command() -> list[str]:
    executable = shutil.which("demucs")
    if executable:
        return [executable]
    return [sys.executable, "-m", "demucs.separate"]
