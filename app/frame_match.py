from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "autocopy.frame_match.v1"


def fps_ratio(fps: float | int | str) -> dict[str, int]:
    fraction = Fraction(str(fps)).limit_denominator(100000)
    return {"num": fraction.numerator, "den": fraction.denominator}


def fps_float(video: Mapping[str, Any]) -> float:
    fps = video["fps"]
    return float(fps["num"]) / float(fps["den"])


def video_metadata(
    path: str | Path,
    *,
    fps: float | int | str,
    frame_count: int | None = None,
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
) -> dict[str, Any]:
    fps_value = float(Fraction(str(fps)))
    if frame_count is None and duration is not None:
        frame_count = round(float(duration) * fps_value)
    return {
        "path": str(Path(path).expanduser().resolve()),
        "fps": fps_ratio(fps),
        "frame_count": int(frame_count) if frame_count is not None else None,
        "width": int(width) if width is not None else None,
        "height": int(height) if height is not None else None,
    }


def metadata_from_video_info(path: str | Path, info: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not info or "fps" not in info:
        return None
    return video_metadata(
        path,
        fps=info["fps"],
        frame_count=info.get("frame_count"),
        width=info.get("width"),
        height=info.get("height"),
        duration=info.get("duration"),
    )


def frame_span(start_frame: int, end_frame_exclusive: int) -> dict[str, int]:
    start = int(start_frame)
    end = max(start, int(end_frame_exclusive))
    return {
        "start_frame": start,
        "end_frame_exclusive": end,
        "frame_count": end - start,
    }


def seconds_range_to_frame_span(values: list[float] | tuple[float, float], fps: float) -> dict[str, int]:
    start_sec, end_sec = [float(value) for value in values]
    start_frame = int(math.floor(start_sec * fps))
    end_frame = int(math.ceil(end_sec * fps))
    if end_frame <= start_frame:
        end_frame = start_frame + 1
    return frame_span(start_frame, end_frame)


def legacy_segment_match(segment: Any, *, index: int, kind: str = "matched") -> dict[str, Any]:
    viral = frame_span(int(segment.viral_start), int(segment.viral_end) + 1)
    source = frame_span(int(segment.source_start), int(segment.source_end) + 1)
    return _match_record(
        index=index,
        kind=kind,
        viral=viral,
        source=source,
        mirrored=bool(segment.flipped),
        crop_x=int(segment.crop_x),
        quality={
            "primary": {
                "name": "legacy_avg_score",
                "value": float(segment.avg_score),
                "higher_is_better": False,
            },
            "metrics": {
                "avg_score": float(segment.avg_score),
                "max_score": float(segment.max_score),
            },
        },
        engine="legacy",
    )


def vmf_segment_match(
    segment: Mapping[str, Any],
    *,
    index: int,
    viral_key: str,
    source_key: str,
    viral_fps: float,
    source_fps: float,
) -> dict[str, Any]:
    viral = seconds_range_to_frame_span(segment[viral_key], viral_fps)
    source = seconds_range_to_frame_span(segment[source_key], source_fps)
    metrics = {
        key: segment.get(key)
        for key in ["inliers", "pvalue", "z_score", "weighted_support", "speed_ratio"]
        if segment.get(key) is not None
    }
    return _match_record(
        index=index,
        kind="matched",
        viral=viral,
        source=source,
        mirrored=bool(segment.get("mirrored", False)),
        crop_x=None,
        quality={
            "primary": {
                "name": "vmf_score",
                "value": segment.get("score"),
                "higher_is_better": True,
            },
            "metrics": metrics,
        },
        engine="vmf",
    )


def build_frame_match_payload(
    *,
    node_type: str,
    engine: str,
    viral_video: Mapping[str, Any],
    source_video: Mapping[str, Any],
    matches: list[Mapping[str, Any]],
    params: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    warnings: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    ordered_matches = [deepcopy(match) for match in sorted(matches, key=lambda item: item["viral"]["start_frame"])]
    for index, match in enumerate(ordered_matches, start=1):
        match["index"] = index
        match["id"] = f"match_{index:04d}"

    viral_total_frames = viral_video.get("frame_count")
    viral_matched_frames = sum(int(match["viral"]["frame_count"]) for match in ordered_matches)
    source_used_frames = sum(int(match["source"]["frame_count"]) for match in ordered_matches)
    unmatched = unmatched_ranges(ordered_matches, viral_total_frames)
    coverage_ratio = None
    if viral_total_frames:
        coverage_ratio = round(viral_matched_frames / int(viral_total_frames), 6)

    return {
        "schema": SCHEMA,
        "producer": {
            "node_type": node_type,
            "engine": engine,
            "engine_version": None,
            "created_at": created_at or datetime.now().astimezone().isoformat(timespec="seconds"),
            "params": dict(params or {}),
        },
        "videos": {
            "viral": dict(viral_video),
            "source": dict(source_video),
        },
        "summary": {
            "match_count": len(ordered_matches),
            "viral_matched_frames": viral_matched_frames,
            "source_used_frames": source_used_frames,
            "viral_total_frames": viral_total_frames,
            "viral_coverage_ratio": coverage_ratio,
            "unmatched_count": len(unmatched),
        },
        "matches": ordered_matches,
        "unmatched": unmatched,
        "artifacts": dict(artifacts or {}),
        "warnings": list(warnings or []),
    }


def unmatched_ranges(matches: list[Mapping[str, Any]], viral_total_frames: int | None) -> list[dict[str, Any]]:
    if not matches:
        if viral_total_frames is None or viral_total_frames <= 0:
            return []
        return [{"viral": frame_span(0, viral_total_frames), "reason": "no_match"}]

    end_limit = int(viral_total_frames) if viral_total_frames is not None else max(
        int(match["viral"]["end_frame_exclusive"]) for match in matches
    )
    cursor = 0
    gaps: list[dict[str, Any]] = []
    for match in matches:
        start = int(match["viral"]["start_frame"])
        end = int(match["viral"]["end_frame_exclusive"])
        if start > cursor:
            gaps.append({"viral": frame_span(cursor, start), "reason": "no_match"})
        cursor = max(cursor, end)
    if cursor < end_limit:
        gaps.append({"viral": frame_span(cursor, end_limit), "reason": "no_match"})
    return gaps


def _match_record(
    *,
    index: int,
    kind: str,
    viral: dict[str, int],
    source: dict[str, int],
    mirrored: bool,
    crop_x: int | None,
    quality: dict[str, Any],
    engine: str,
) -> dict[str, Any]:
    return {
        "id": f"match_{index:04d}",
        "index": index,
        "kind": kind,
        "viral": viral,
        "source": source,
        "mapping": {
            "type": "linear",
            "source_per_viral": {
                "num": source["frame_count"],
                "den": max(1, viral["frame_count"]),
            },
            "rounding": "nearest",
        },
        "transform": {
            "mirrored": mirrored,
            "crop": {
                "x": crop_x,
                "y": None,
                "width": None,
                "height": None,
                "unit": "px",
            },
        },
        "quality": quality,
        "engine": {"name": engine},
    }
