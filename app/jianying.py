from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


DEFAULT_DRAFT_FOLDER = Path.home() / "Movies/JianyingPro/User Data/Projects/com.lveditor.draft"


def safe_draft_name(video_path: str | Path) -> str:
    name = Path(video_path).stem.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    return name or "autocopy"


def video_info(video_path: str | Path) -> tuple[int, int, float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"]), float(stream["duration"])


def create_jianying_draft(final_video: str | Path, viral_video: str | Path, draft_folder: str | Path = DEFAULT_DRAFT_FOLDER) -> Path:
    import pycapcut as cc

    final_video = Path(final_video).resolve()
    draft_folder = Path(draft_folder).expanduser()
    draft_folder.mkdir(parents=True, exist_ok=True)
    width, height, duration = video_info(final_video)
    script = cc.DraftFolder(str(draft_folder)).create_draft(
        safe_draft_name(viral_video),
        width,
        height,
        allow_replace=True,
    )
    script.add_track(cc.TrackType.video)
    script.add_segment(cc.VideoSegment(str(final_video), cc.trange(0, duration)))
    script.save()
    return draft_folder / safe_draft_name(viral_video)
