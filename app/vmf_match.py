from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from app.frame_match import (
    build_frame_match_payload,
    fps_float,
    metadata_from_video_info,
    video_metadata,
    vmf_segment_match,
)
from app.model_cache import model_cache_env


DEFAULT_VMF_MODEL = "dinov2_vits14"
VMF_MODELS = ("dinov2_vits14", "dinov2_vitb14")


def run_vmf_match(
    viral_path: str | Path,
    source_path: str | Path,
    output_dir: str | Path,
    *,
    viral_video_info: Mapping[str, Any] | None = None,
    source_video_info: Mapping[str, Any] | None = None,
    vmf_bin: str = "vmf",
    fps: float = 2.0,
    model: str = DEFAULT_VMF_MODEL,
    device: str = "auto",
    no_mirror: bool = False,
    keyframes_only: bool = False,
    no_cropdetect: bool = False,
    legacy_ransac: bool = False,
) -> dict[str, str]:
    """Run video-match-finder and convert its overlaps into frame match JSON."""
    resolved_vmf_bin = _resolve_vmf_bin(vmf_bin)
    if resolved_vmf_bin is None:
        raise RuntimeError(
            f"VMF command not found: {vmf_bin}. Install https://github.com/Sinoosoida/video-match-finder "
            "and make sure the `vmf` command is on PATH or next to the current Python executable."
        )

    viral = Path(viral_path).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve()
    work_dir = out_dir / "vmf_work"
    data_dir = work_dir / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    vmf_results_json = work_dir / "vmf_results.json"
    segments_json = work_dir / "segments.json"
    resolved_model = _resolve_vmf_model(model)

    cmd = [
        resolved_vmf_bin,
        "scan",
        str(viral),
        str(source),
        "--data-dir",
        str(data_dir),
        "--json",
        str(vmf_results_json),
        "--fps",
        str(fps),
        "--model",
        resolved_model,
        "--device",
        device,
    ]
    if no_mirror:
        cmd.append("--no-mirror")
    if keyframes_only:
        cmd.append("--keyframes-only")
    if no_cropdetect:
        cmd.append("--no-cropdetect")
    if legacy_ransac:
        cmd.append("--legacy-ransac")

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_vmf_env())
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(_format_vmf_process_error(exc)) from exc
    raw_results = json.loads(vmf_results_json.read_text(encoding="utf-8"))
    viral_metadata = metadata_from_video_info(viral, viral_video_info) or _probe_video_metadata(viral)
    source_metadata = metadata_from_video_info(source, source_video_info) or _probe_video_metadata(source)
    matches = _extract_matches(raw_results, viral, source, viral_metadata, source_metadata)
    warnings = []
    if not matches:
        warnings.append("VMF did not find matching segments for the selected video pair")

    payload = build_frame_match_payload(
        node_type="VideoMatchVMF",
        engine="vmf",
        viral_video=viral_metadata,
        source_video=source_metadata,
        matches=matches,
        params={
            "vmf_bin": vmf_bin,
            "fps": fps,
            "model": resolved_model,
            "device": device,
            "no_mirror": no_mirror,
            "keyframes_only": keyframes_only,
            "no_cropdetect": no_cropdetect,
            "legacy_ransac": legacy_ransac,
        },
        artifacts={"raw_engine_result": str(vmf_results_json)},
        warnings=warnings,
    )
    segments_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "segments_json": str(segments_json),
        "vmf_results_json": str(vmf_results_json),
    }


def _resolve_vmf_bin(vmf_bin: str) -> str | None:
    resolved = shutil.which(vmf_bin)
    if resolved:
        return resolved

    if _is_path_like_command(vmf_bin):
        candidate = Path(vmf_bin).expanduser()
        if _is_executable_file(candidate):
            return str(candidate.resolve())
        return None

    python_executable = Path(sys.executable).expanduser()
    python_dirs = [python_executable.parent]
    resolved_python_dir = python_executable.resolve().parent
    if resolved_python_dir != python_dirs[0]:
        python_dirs.append(resolved_python_dir)

    for python_dir in python_dirs:
        adjacent = python_dir / vmf_bin
        if _is_executable_file(adjacent):
            return str(adjacent.resolve())
    return None


def _is_path_like_command(command: str) -> bool:
    return Path(command).is_absolute() or "/" in command or "\\" in command


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _vmf_env() -> dict[str, str]:
    env = model_cache_env()
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["VECLIB_MAXIMUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"
    return env


def _resolve_vmf_model(model: str | None) -> str:
    value = str(model or "").strip()
    if value in VMF_MODELS:
        return value
    return DEFAULT_VMF_MODEL


def _format_vmf_process_error(exc: subprocess.CalledProcessError) -> str:
    parts = [f"VMF command failed with exit code {exc.returncode}: {exc.cmd}"]
    stdout = _decode_process_output(exc.stdout or exc.output)
    stderr = _decode_process_output(exc.stderr)
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    return "\n\n".join(parts)


def _decode_process_output(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip()
    return str(value).rstrip()


def _extract_matches(
    raw_results: list[dict[str, Any]],
    viral: Path,
    source: Path,
    viral_video: Mapping[str, Any],
    source_video: Mapping[str, Any],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for result in raw_results:
        a_path = Path(result.get("a", {}).get("path", "")).expanduser().resolve()
        b_path = Path(result.get("b", {}).get("path", "")).expanduser().resolve()
        if a_path == viral and b_path == source:
            viral_key = "a_range"
            source_key = "b_range"
        elif a_path == source and b_path == viral:
            viral_key = "b_range"
            source_key = "a_range"
        else:
            continue

        for segment in result.get("segments", []):
            matches.append(
                vmf_segment_match(
                    segment,
                    index=len(matches) + 1,
                    viral_key=viral_key,
                    source_key=source_key,
                    viral_fps=fps_float(viral_video),
                    source_fps=fps_float(source_video),
                )
            )

    matches.sort(key=lambda item: item["viral"]["start_frame"])
    for index, match in enumerate(matches, start=1):
        match["index"] = index
        match["id"] = f"match_{index:04d}"
    return matches


def _probe_video_metadata(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,duration,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream = json.loads(result.stdout)["streams"][0]
    fps_value = stream.get("avg_frame_rate", "0/1")
    duration = float(stream.get("duration") or 0)
    frame_count = stream.get("nb_frames")
    return video_metadata(
        path,
        fps=fps_value,
        frame_count=int(frame_count) if frame_count and frame_count != "N/A" else None,
        width=stream.get("width"),
        height=stream.get("height"),
        duration=duration,
    )
