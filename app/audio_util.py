import hashlib
import subprocess
from pathlib import Path


def file_md5(path: str | Path) -> str:
    digest = hashlib.md5()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def separate_vocals(video_path: str | Path) -> Path:
    video = Path(video_path)
    if not video.is_file():
        raise FileNotFoundError(video)

    output_dir = Path.cwd() / "output" / "audio" / file_md5(video) / "separated"
    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["demucs", "--two-stems", "vocals", "-o", str(output_dir), str(video)],
        check=True,
    )
    return output_dir
