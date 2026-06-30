from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from app.copied.srt_llm_rewriter import parse_srt
from app.frame_match import fps_float


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


def create_jianying_merge_draft(
    segments_json: str | Path,
    srt_path: str | Path,
    *,
    draft_folder: str | Path = DEFAULT_DRAFT_FOLDER,
    draft_name: str | None = None,
) -> Path:
    import pycapcut as cc

    frame_match = _read_frame_match_json(segments_json)
    viral = frame_match["videos"]["viral"]
    source = frame_match["videos"]["source"]
    viral_fps = fps_float(viral)
    source_fps = fps_float(source)
    width = int(viral.get("width") or source.get("width") or 1080)
    height = int(viral.get("height") or source.get("height") or 1920)
    source_path = Path(source["path"]).expanduser().resolve()
    draft_folder = Path(draft_folder).expanduser()
    draft_folder.mkdir(parents=True, exist_ok=True)
    name = safe_draft_name(draft_name or viral.get("path") or source_path)

    script = cc.DraftFolder(str(draft_folder)).create_draft(
        name,
        width,
        height,
        fps=max(1, round(viral_fps)),
        allow_replace=True,
    )
    script.add_track(cc.TrackType.video, "matched_video")
    for match in frame_match["matches"]:
        viral_start, viral_duration = _span_seconds(match["viral"], viral_fps)
        source_start, source_duration = _span_seconds(match["source"], source_fps)
        if viral_duration <= 0 or source_duration <= 0:
            continue
        script.add_segment(
            cc.VideoSegment(
                str(source_path),
                cc.trange(viral_start, viral_duration),
                source_timerange=cc.trange(source_start, source_duration),
                speed=source_duration / viral_duration,
            ),
            "matched_video",
        )

    script.add_track(cc.TrackType.text, "srt_subtitles")
    style = cc.TextStyle(
        size=8.0,
        bold=True,
        color=(1.0, 1.0, 1.0),
        align=1,
        auto_wrapping=True,
        max_line_width=0.82,
    )
    border = cc.TextBorder(width=14.0, color=(0.0, 0.0, 0.0), alpha=1.0)
    for entry in parse_srt(srt_path):
        duration = max(0.001, (entry.end_ms - entry.start_ms) / 1000)
        script.add_segment(
            cc.TextSegment(
                entry.text,
                cc.trange(entry.start_ms / 1000, duration),
                style=style,
                border=border,
            ),
            "srt_subtitles",
        )
    script.save()
    return draft_folder / name


def _read_frame_match_json(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "autocopy.frame_match.v1":
        raise ValueError("frame match JSON is required")
    if "matches" not in data or not isinstance(data["matches"], list):
        raise ValueError("frame match JSON does not contain matches")
    return data


def _span_seconds(span: dict, fps: float) -> tuple[float, float]:
    start_frame = int(span["start_frame"])
    frame_count = int(span.get("frame_count", int(span["end_frame_exclusive"]) - start_frame))
    return start_frame / fps, frame_count / fps
