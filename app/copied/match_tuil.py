#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "scipy"]
# ///
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.spatial import cKDTree

from app.frame_match import build_frame_match_payload, legacy_segment_match, video_metadata

try:
    import torch
except ImportError:  # pragma: no cover - CPU-only install
    torch = None


CHUNK_SECONDS = 180
CROP_STEP = 40
FEATURE_SIZE = 18
SCORE_PERCENTILE = 99
MIN_FRAMES = 1
MIN_SEGMENT_FRAMES = 12
CANDIDATE_TOP_K = 20
MAX_CANDIDATES_PER_FRAME = 160
SHORT_SEGMENT_FRAMES = 30
TINY_SEGMENT_FRAMES = 3
BAD_SHORT_SEGMENT_SCORE = 13.0
BAD_SEGMENT_SCORE = 14.5
OFFSET_TOLERANCE = 10
CROP_TOLERANCE = 400
SHORT_OFFSET_TOLERANCE = 120
SOURCE_CACHE_DIR = "source_cache"
GPU_SOURCE_CACHE_DIR = "source_cache_gpu"
RUNS_DIR = "runs"


@dataclass(frozen=True)
class Match:
    viral_frame: int
    source_frame: int
    score: float
    crop_x: int
    flipped: bool


@dataclass(frozen=True)
class CandidateMatch:
    viral_frame: int
    source_frame: int
    score: float
    crop_x: int
    flipped: bool


@dataclass(frozen=True)
class Segment:
    viral_start: int
    viral_end: int
    source_start: int
    source_end: int
    crop_x: int
    flipped: bool
    avg_score: float
    max_score: float

    @property
    def frame_count(self) -> int:
        return self.viral_end - self.viral_start + 1


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ffprobe(path: Path, entry: str) -> str:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            f"stream={entry}",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ]
    )
    return result.stdout.decode().strip()


def ffprobe_format(path: Path, entry: str) -> str:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            f"format={entry}",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ]
    )
    return result.stdout.decode().strip()


def fps(path: Path) -> float:
    return float(Fraction(ffprobe(path, "avg_frame_rate")))


def duration(path: Path) -> float:
    value = ffprobe(path, "duration")
    if value and value != "N/A":
        return float(value)
    value = ffprobe_format(path, "duration")
    return float(value) if value and value != "N/A" else 0.0


def frame_count(path: Path, fallback_fps: float) -> int:
    value = ffprobe(path, "nb_frames")
    return int(value) if value and value != "N/A" else round(duration(path) * fallback_fps)


def dimensions(path: Path) -> tuple[int, int]:
    return int(ffprobe(path, "width")), int(ffprobe(path, "height"))


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_cache_dir(source_path: Path, base_dir: Path) -> Path:
    return base_dir / SOURCE_CACHE_DIR / file_md5(source_path)


def run_dir(viral_path: Path, base_dir: Path) -> Path:
    return base_dir / RUNS_DIR / file_md5(viral_path)


def read_scaled_gray(
    path: Path,
    width: int,
    height: int,
    start_sec: float | None = None,
    duration_sec: float | None = None,
    frames: int | None = None,
) -> np.ndarray:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start_sec is not None:
        cmd += ["-ss", f"{start_sec:.9f}"]
    cmd += ["-i", str(path)]
    if duration_sec is not None:
        cmd += ["-t", f"{duration_sec:.9f}"]
    if frames is not None:
        cmd += ["-frames:v", str(frames)]
    cmd += [
        "-vf",
        f"scale={width}:{height}:flags=bicubic,format=gray",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    result = run(cmd)
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    frame_size = width * height
    usable = (raw.size // frame_size) * frame_size
    return raw[:usable].reshape((-1, height, width))


def block_mean(frames: np.ndarray, out_size: int) -> np.ndarray:
    n, h, w = frames.shape
    by = h // out_size
    bx = w // out_size
    return frames[:, : by * out_size, : bx * out_size].reshape(
        n, out_size, by, out_size, bx
    ).mean(axis=(2, 4))


def normalize(features: np.ndarray) -> np.ndarray:
    features = features.astype(np.float32, copy=False)
    features -= features.mean(axis=1, keepdims=True)
    features /= np.maximum(features.std(axis=1, keepdims=True), 1.0)
    return features


def viral_features(path: Path) -> np.ndarray:
    frames = read_scaled_gray(path, 108, 108)
    small = block_mean(frames, FEATURE_SIZE)
    return normalize(small.reshape((small.shape[0], -1)))


def source_features(
    path: Path,
    start_sec: float,
    duration_sec: float,
    source_fps: float,
) -> tuple[np.ndarray, list[tuple[int, int, bool]]]:
    frames = read_scaled_gray(path, 192, 108, start_sec, duration_sec)
    scaled_crop_width = 108
    max_scaled_x = 192 - scaled_crop_width
    scaled_step = max(1, round(CROP_STEP / 10))
    scaled_xs = list(range(0, max_scaled_x + 1, scaled_step))
    if scaled_xs[-1] != max_scaled_x:
        scaled_xs.append(max_scaled_x)

    chunks: list[np.ndarray] = []
    meta: list[tuple[int, int, bool]] = []
    source_start_frame = round(start_sec * source_fps)
    for scaled_x in scaled_xs:
        original_x = min(840, max(0, round(scaled_x * 10)))
        crop = frames[:, :, scaled_x : scaled_x + scaled_crop_width]
        for flipped in (False, True):
            work = crop[:, :, ::-1] if flipped else crop
            small = block_mean(work, FEATURE_SIZE)
            chunks.append(small.reshape((small.shape[0], -1)))
            meta.extend((source_start_frame + i, original_x, flipped) for i in range(frames.shape[0]))
    return normalize(np.vstack(chunks)), meta


def cached_source_features(
    path: Path,
    start_sec: float,
    duration_sec: float,
    source_fps: float,
    cache_dir: Path,
    window: int,
    windows: int,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cache_dir / "meta.json"
    expected_meta = {
        "fps": source_fps,
        "chunk_seconds": CHUNK_SECONDS,
        "crop_step": CROP_STEP,
        "feature_size": FEATURE_SIZE,
        "windows": windows,
    }
    if meta_path.exists() and json.loads(meta_path.read_text()) != expected_meta:
        for old_window in cache_dir.glob("window_*.npz"):
            old_window.unlink()
    if not meta_path.exists() or json.loads(meta_path.read_text()) != expected_meta:
        meta_path.write_text(json.dumps(expected_meta, indent=2, ensure_ascii=False))

    feature_path = cache_dir / f"window_{window:04d}.npz"
    if feature_path.exists():
        log(f"loading source cache {window + 1}/{windows}: {feature_path}")
        data = np.load(feature_path)
        return data["features"], (data["source_frames"], data["crop_xs"], data["flipped"])

    log(f"building source cache {window + 1}/{windows}: {start_sec:.1f}s + {duration_sec:.1f}s")
    sf, meta = source_features(path, start_sec, duration_sec, source_fps)
    source_frames = np.array([item[0] for item in meta], dtype=np.int32)
    crop_xs = np.array([item[1] for item in meta], dtype=np.int16)
    flipped = np.array([item[2] for item in meta], dtype=np.bool_)
    np.savez(feature_path, features=sf, source_frames=source_frames, crop_xs=crop_xs, flipped=flipped)
    return sf, (source_frames, crop_xs, flipped)


def gpu_available() -> bool:
    return torch is not None and torch.cuda.is_available()


def gpu_source_cache_dir(source_path: Path, base_dir: Path) -> Path:
    return base_dir / GPU_SOURCE_CACHE_DIR / file_md5(source_path)


def source_features_gpu(
    path: Path,
    start_sec: float,
    duration_sec: float,
    source_fps: float,
    cache_dir: Path,
    window: int,
) -> tuple["torch.Tensor", np.ndarray, np.ndarray, np.ndarray]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    feature_path = cache_dir / f"window_{window:04d}.pt"
    if feature_path.exists():
        log(f"loading gpu source cache {window + 1}: {feature_path}")
        data = torch.load(feature_path, map_location="cpu")
        return (
            data["features"].cuda(non_blocking=True),
            data["source_frames"].numpy(),
            data["crop_xs"].numpy(),
            data["flipped"].numpy(),
        )

    log(f"building gpu source cache {window + 1}: {start_sec:.1f}s + {duration_sec:.1f}s")
    frames = torch.from_numpy(read_scaled_gray(path, 192, 108, start_sec, duration_sec).copy()).cuda().float()
    scaled_crop_width = 108
    max_scaled_x = 192 - scaled_crop_width
    scaled_step = max(1, round(CROP_STEP / 10))
    scaled_xs = list(range(0, max_scaled_x + 1, scaled_step))
    if scaled_xs[-1] != max_scaled_x:
        scaled_xs.append(max_scaled_x)

    feature_parts: list["torch.Tensor"] = []
    source_frames: list[int] = []
    crop_xs: list[int] = []
    flipped_meta: list[bool] = []
    source_start_frame = round(start_sec * source_fps)
    for scaled_x in scaled_xs:
        original_x = min(840, max(0, round(scaled_x * 10)))
        crop = frames[:, :, scaled_x : scaled_x + scaled_crop_width]
        for is_flipped in (False, True):
            work = torch.flip(crop, dims=[2]) if is_flipped else crop
            small = torch.nn.functional.avg_pool2d(work[:, None], kernel_size=6, stride=6).flatten(1)
            small = small - small.mean(dim=1, keepdim=True)
            small = small / torch.clamp(small.std(dim=1, keepdim=True), min=1.0)
            feature_parts.append(small)
            source_frames.extend(source_start_frame + i for i in range(frames.shape[0]))
            crop_xs.extend(original_x for _ in range(frames.shape[0]))
            flipped_meta.extend(is_flipped for _ in range(frames.shape[0]))

    features = torch.cat(feature_parts).contiguous()
    source_frames_np = np.array(source_frames, dtype=np.int32)
    crop_xs_np = np.array(crop_xs, dtype=np.int16)
    flipped_np = np.array(flipped_meta, dtype=np.bool_)
    torch.save(
        {
            "features": features.cpu(),
            "source_frames": torch.from_numpy(source_frames_np),
            "crop_xs": torch.from_numpy(crop_xs_np.astype(np.int32)),
            "flipped": torch.from_numpy(flipped_np),
        },
        feature_path,
    )
    return features, source_frames_np, crop_xs_np, flipped_np


def add_gpu_candidates(
    vf: np.ndarray,
    sf: "torch.Tensor",
    source_frames: np.ndarray,
    crop_xs: np.ndarray,
    flipped: np.ndarray,
    out: dict[int, list[CandidateMatch]],
    batch: int = 256,
) -> None:
    k = min(CANDIDATE_TOP_K, len(source_frames))
    for start in range(0, len(vf), batch):
        query = torch.from_numpy(vf[start : start + batch]).cuda()
        distances = torch.cdist(query, sf)
        values, indexes = torch.topk(distances, k=k, largest=False, dim=1)
        for row, (value_row, index_row) in enumerate(zip(values.cpu().numpy(), indexes.cpu().numpy())):
            viral_frame = start + row
            for distance, index in zip(value_row, index_row):
                out[viral_frame].append(
                    CandidateMatch(
                        viral_frame,
                        int(source_frames[index]),
                        float(distance),
                        int(crop_xs[index]),
                        bool(flipped[index]),
                    )
                )


def choose_temporal_matches(candidates_by_frame: dict[int, list[CandidateMatch]]) -> list[Match]:
    frames = sorted(candidates_by_frame)
    chosen: list[CandidateMatch] = []
    previous: CandidateMatch | None = None
    for frame in frames:
        candidates = sorted(candidates_by_frame[frame], key=lambda item: item.score)[:MAX_CANDIDATES_PER_FRAME]
        best = candidates[0]
        if previous is None:
            chosen.append(best)
            previous = best
            continue
        viral_step = frame - previous.viral_frame
        continuous = [
            candidate
            for candidate in candidates
            if abs((candidate.source_frame - previous.source_frame) - viral_step) <= OFFSET_TOLERANCE
            and abs(candidate.crop_x - previous.crop_x) <= CROP_TOLERANCE
            and candidate.flipped == previous.flipped
        ]
        # ponytail: local continuity only; cuts are allowed when the continuous candidate is much worse.
        if continuous and continuous[0].score <= best.score + 2.5:
            best = continuous[0]
        chosen.append(best)
        previous = best
    return [Match(c.viral_frame, c.source_frame, c.score, c.crop_x, c.flipped) for c in chosen]


def find_matches_cpu(viral_path: Path, source_path: Path, source_fps: float, cache_dir: Path) -> list[Match]:
    log("extracting viral features...")
    vf = viral_features(viral_path)
    candidates_by_frame: dict[int, list[CandidateMatch]] = {i: [] for i in range(len(vf))}
    total = duration(source_path)
    windows = max(1, int(np.ceil(total / CHUNK_SECONDS)))

    for window in range(windows):
        start = window * CHUNK_SECONDS
        length = min(CHUNK_SECONDS, total - start) if total else CHUNK_SECONDS
        sf, meta = cached_source_features(source_path, start, length, source_fps, cache_dir, window, windows)
        source_frames, crop_xs, flipped = meta
        k = min(CANDIDATE_TOP_K, len(sf))
        distances, indexes = cKDTree(sf).query(vf, k=k, workers=-1)
        if k == 1:
            distances = distances[:, None]
            indexes = indexes[:, None]
        for viral_frame, rows in enumerate(zip(distances, indexes)):
            distance_row, index_row = rows
            for distance, index in zip(distance_row, index_row):
                source_frame = source_frames[int(index)]
                candidates_by_frame[viral_frame].append(
                    CandidateMatch(
                        viral_frame,
                        int(source_frame),
                        float(distance),
                        int(crop_xs[int(index)]),
                        bool(flipped[int(index)]),
                    )
                )

    return choose_temporal_matches(candidates_by_frame)


def find_matches_gpu(viral_path: Path, source_path: Path, source_fps: float, cache_dir: Path) -> list[Match]:
    if not gpu_available():
        log("GPU unavailable, falling back to CPU matching")
        return find_matches_cpu(viral_path, source_path, source_fps, source_cache_dir(source_path, Path.cwd()))

    log(f"extracting viral features on CPU; matching on {torch.cuda.get_device_name(0)}...")
    vf = viral_features(viral_path)
    candidates_by_frame: dict[int, list[CandidateMatch]] = {i: [] for i in range(len(vf))}
    total = duration(source_path)
    windows = max(1, int(np.ceil(total / CHUNK_SECONDS)))
    for window in range(windows):
        start_time = time.time()
        start = window * CHUNK_SECONDS
        length = min(CHUNK_SECONDS, total - start) if total else CHUNK_SECONDS
        sf, source_frames, crop_xs, flipped = source_features_gpu(source_path, start, length, source_fps, cache_dir, window)
        add_gpu_candidates(vf, sf, source_frames, crop_xs, flipped, candidates_by_frame)
        log(f"gpu window {window + 1}/{windows} done in {time.time() - start_time:.1f}s")
    return choose_temporal_matches(candidates_by_frame)


def find_matches(viral_path: Path, source_path: Path, source_fps: float, cache_dir: Path, use_gpu: bool = False) -> list[Match]:
    if use_gpu:
        return find_matches_gpu(viral_path, source_path, source_fps, cache_dir)
    return find_matches_cpu(viral_path, source_path, source_fps, cache_dir)


def build_segments(matches: Iterable[Match]) -> list[Segment]:
    matches = list(matches)
    threshold = float(np.percentile([m.score for m in matches], SCORE_PERCENTILE))
    log(f"score threshold: {threshold:.3f}")
    segments: list[Segment] = []
    current: list[Match] = []

    def median_offset(items: list[Match]) -> int:
        return int(round(float(np.median([m.source_frame - m.viral_frame for m in items]))))

    def flush() -> None:
        if len(current) < MIN_FRAMES:
            return
        offset = median_offset(current)
        scores = [m.score for m in current]
        crop_x = int(round(float(np.median([m.crop_x for m in current]))))
        segments.append(
            Segment(
                current[0].viral_frame,
                current[-1].viral_frame,
                current[0].viral_frame + offset,
                current[-1].viral_frame + offset,
                crop_x,
                current[0].flipped,
                float(np.mean(scores)),
                float(np.max(scores)),
            )
        )

    for match in matches:
        if match.score > threshold:
            flush()
            current = []
            continue
        if not current:
            current = [match]
            continue
        expected_offset = median_offset(current[-12:])
        same_run = (
            match.viral_frame == current[-1].viral_frame + 1
            and abs((match.source_frame - match.viral_frame) - expected_offset) <= OFFSET_TOLERANCE
            and abs(match.crop_x - current[-1].crop_x) <= CROP_TOLERANCE
            and match.flipped == current[-1].flipped
        )
        if (
            same_run
        ):
            current.append(match)
        else:
            flush()
            current = [match]
    flush()
    segments = smooth_short_segments(segments)
    segments = drop_bad_segments(segments)
    segments = optimize_segment_boundaries(segments)
    return [segment for segment in segments if segment.frame_count >= MIN_SEGMENT_FRAMES]


def merge_segments(left: Segment, right: Segment) -> Segment:
    frames = left.frame_count + right.frame_count
    return Segment(
        left.viral_start,
        right.viral_end,
        left.source_start,
        right.source_end,
        int(round((left.crop_x * left.frame_count + right.crop_x * right.frame_count) / frames)),
        left.flipped,
        (left.avg_score * left.frame_count + right.avg_score * right.frame_count) / frames,
        max(left.max_score, right.max_score),
    )


def can_coalesce(left: Segment, right: Segment) -> bool:
    viral_gap = right.viral_start - left.viral_end
    source_gap = right.source_start - left.source_end
    return (
        viral_gap == 1
        and source_gap == 1
        and left.flipped == right.flipped
        and abs(left.crop_x - right.crop_x) <= CROP_TOLERANCE
    )


def extend_segment(segment: Segment, viral_start: int, viral_end: int) -> Segment:
    offset = segment.source_start - segment.viral_start
    return Segment(
        viral_start,
        viral_end,
        viral_start + offset,
        viral_end + offset,
        segment.crop_x,
        segment.flipped,
        segment.avg_score,
        segment.max_score,
    )


def segment_offset(segment: Segment) -> int:
    return segment.source_start - segment.viral_start


def offset_delta(left: Segment, right: Segment) -> int:
    return abs(segment_offset(left) - segment_offset(right))


def smooth_short_segments(segments: list[Segment]) -> list[Segment]:
    if len(segments) < 2:
        return segments

    segments = bridge_short_timeline_jumps(segments)
    smoothed: list[Segment] = []
    index = 0
    while index < len(segments):
        segment = segments[index]
        if segment.frame_count > SHORT_SEGMENT_FRAMES:
            smoothed.append(segment)
            index += 1
            continue

        previous = smoothed[-1] if smoothed else None
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        previous_delta = offset_delta(previous, segment) if previous else 10**9
        next_delta = offset_delta(segment, next_segment) if next_segment else 10**9
        if previous is None and next_segment is None:
            smoothed.append(segment)
        elif segment.frame_count <= TINY_SEGMENT_FRAMES and (
            previous is None or (next_segment is not None and next_segment.frame_count > previous.frame_count)
        ):
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        elif segment.frame_count <= TINY_SEGMENT_FRAMES and previous is not None:
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif (
            previous is not None
            and next_segment is not None
            and offset_delta(previous, next_segment) <= SHORT_OFFSET_TOLERANCE
        ):
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif previous is None and next_delta <= SHORT_OFFSET_TOLERANCE:
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        elif next_segment is None and previous_delta <= SHORT_OFFSET_TOLERANCE:
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif previous_delta <= SHORT_OFFSET_TOLERANCE and (
            next_delta > SHORT_OFFSET_TOLERANCE or previous.frame_count >= next_segment.frame_count
        ):
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif next_delta <= SHORT_OFFSET_TOLERANCE:
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        else:
            smoothed.append(segment)
        index += 1

    coalesced: list[Segment] = []
    for segment in smoothed:
        if coalesced and can_coalesce(coalesced[-1], segment):
            coalesced[-1] = merge_segments(coalesced[-1], segment)
        else:
            coalesced.append(segment)
    return coalesced


def is_bad_segment(segment: Segment, previous: Segment | None, next_segment: Segment | None) -> bool:
    if segment.frame_count <= SHORT_SEGMENT_FRAMES and segment.avg_score >= BAD_SHORT_SEGMENT_SCORE:
        return True
    if segment.avg_score < BAD_SEGMENT_SCORE:
        return False
    previous_jump = previous is not None and offset_delta(previous, segment) > SHORT_OFFSET_TOLERANCE
    next_jump = next_segment is not None and offset_delta(segment, next_segment) > SHORT_OFFSET_TOLERANCE
    return previous_jump or next_jump


def drop_bad_segments(segments: list[Segment]) -> list[Segment]:
    clean: list[Segment] = []
    for index, segment in enumerate(segments):
        previous = clean[-1] if clean else None
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        if not is_bad_segment(segment, previous, next_segment):
            clean.append(segment)
    return clean


def optimize_segment_boundaries(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []

    optimized = [segments[0]]
    for segment in segments[1:]:
        previous = optimized[-1]
        gap = segment.viral_start - previous.viral_end - 1
        if 0 < gap <= SHORT_SEGMENT_FRAMES and offset_delta(previous, segment) <= SHORT_OFFSET_TOLERANCE:
            optimized[-1] = extend_segment(previous, previous.viral_start, segment.viral_start - 1)

        if optimized and can_coalesce(optimized[-1], segment):
            optimized[-1] = merge_segments(optimized[-1], segment)
        else:
            optimized.append(segment)
    return optimized


def fill_gaps_by_extending_previous(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []
    filled = [segments[0]]
    for segment in segments[1:]:
        previous = filled[-1]
        gap = segment.viral_start - previous.viral_end - 1
        if gap > 0:
            filled.append(
                Segment(
                    previous.viral_end + 1,
                    segment.viral_start - 1,
                    previous.source_end + 1,
                    previous.source_end + gap,
                    previous.crop_x,
                    previous.flipped,
                    previous.avg_score,
                    previous.max_score,
                )
            )
        filled.append(segment)
    return filled


def bridge_short_timeline_jumps(segments: list[Segment]) -> list[Segment]:
    bridged: list[Segment] = []
    index = 0
    while index < len(segments):
        previous = bridged[-1] if bridged else None
        segment = segments[index]
        if previous is None or segment.frame_count > SHORT_SEGMENT_FRAMES or offset_delta(previous, segment) <= SHORT_OFFSET_TOLERANCE:
            bridged.append(segment)
            index += 1
            continue

        start = index
        while index < len(segments) and segments[index].frame_count <= SHORT_SEGMENT_FRAMES and offset_delta(previous, segments[index]) > SHORT_OFFSET_TOLERANCE:
            index += 1
        next_segment = segments[index] if index < len(segments) else None
        if next_segment is not None and offset_delta(previous, next_segment) <= SHORT_OFFSET_TOLERANCE:
            bridged[-1] = extend_segment(previous, previous.viral_start, segments[index - 1].viral_end)
        else:
            bridged.extend(segments[start:index])
    return bridged


def write_csv(matches: list[Match], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(matches[0]).keys()))
        writer.writeheader()
        for match in matches:
            writer.writerow(asdict(match))


def write_html(viral_path: Path, output_video: Path, output_html: Path, segments: list[Segment]) -> None:
    segment_json = json.dumps([asdict(s) | {"frame_count": s.frame_count} for s in segments], ensure_ascii=False)
    viral_src = viral_path.resolve().as_uri()
    output_src = output_video.name
    template = next(
        (
            path
            for path in [
                Path.cwd() / "review_sync.html",
                Path("/Users/chaiyapeng/Downloads/LHL/金海/review_sync.html"),
            ]
            if path.exists()
        ),
        None,
    )
    if template:
        html = template.read_text()
        total_frames = sum(s.frame_count for s in segments)
        html = re.sub(r"const TOTAL_FRAMES = \d+;", f"const TOTAL_FRAMES = {total_frames};", html)
        html = re.sub(r"const segments = \[.*?\];", f"const segments = {segment_json};", html, flags=re.S)
        html = re.sub(r'<video id="viral" src="[^"]+"', f'<video id="viral" src="{viral_src}"', html)
        html = re.sub(r'<video id="matched" src="[^"]+"', f'<video id="matched" src="{output_src}"', html)
        html = html.replace(
            "</style>",
            """
    .app {
      grid-template-rows: minmax(264px, 55vh) auto;
    }

    video {
      min-height: 216px;
      max-height: 50vh;
    }

    @media (max-width: 900px) {
      .app {
        grid-template-rows: auto auto;
      }

      video {
        min-height: 180px;
        max-height: 38vh;
      }
    }
  </style>""",
        )
        output_html.write_text(html)
        return

    output_html.write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<title>视频匹配核查</title>
<style>
body{{margin:0;background:#111315;color:#eee;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
main{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}}
video{{width:100%;background:#000}}
pre{{grid-column:1/-1;white-space:pre-wrap;font-size:12px;color:#bbb}}
</style>
<main>
<video controls src="{viral_src}"></video>
<video controls src="{output_src}"></video>
<pre id="segments"></pre>
</main>
<script>
const segments = {segment_json};
document.getElementById("segments").textContent = JSON.stringify(segments, null, 2);
</script>
"""
    )


def cut_segments(source_path: Path, segments: list[Segment], source_fps: float, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    for index, segment in enumerate(segments, start=1):
        log(f"cutting shot {index:03d}/{len(segments)} frames={segment.frame_count}")
        vf = "hflip" if segment.flipped else "null"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{segment.source_start / source_fps:.9f}",
                "-i",
                str(source_path),
                "-frames:v",
                str(segment.frame_count),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "16",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                str(output_dir / f"shot{index:03d}.mp4"),
            ]
        )


def concat(shots_dir: Path, count: int, work_dir: Path, output_video: Path) -> None:
    log("concatenating shots...")
    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{(shots_dir / f'shot{i:03d}.mp4').resolve()}'\n" for i in range(1, count + 1))
    )
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(output_video)])


def match_frames(viral_path: str | Path, source_path: str | Path, output_dir: str | Path | None = None, use_gpu: bool = False) -> dict[str, object]:
    viral_path = Path(viral_path).expanduser().resolve()
    source_path = Path(source_path).expanduser().resolve()
    base_dir = Path.cwd()
    output_dir = Path(output_dir).expanduser().resolve() if output_dir else run_dir(viral_path, base_dir)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    source_fps = fps(source_path)
    viral_fps = fps(viral_path)
    source_frames = frame_count(source_path, source_fps)
    viral_frames = frame_count(viral_path, viral_fps)
    viral_width, viral_height = dimensions(viral_path)
    source_width, source_height = dimensions(source_path)
    log(f"viral: {viral_path}")
    log(f"source: {source_path}")
    log(f"output: {output_dir}")
    log(f"fps: viral={viral_fps:.3f}, source={source_fps:.3f}")
    use_gpu = use_gpu and gpu_available()
    cache_dir = gpu_source_cache_dir(source_path, base_dir) if use_gpu else source_cache_dir(source_path, base_dir)
    log(f"source cache: {cache_dir}")
    log(f"gpu enabled: {use_gpu}")

    matches = find_matches(viral_path, source_path, source_fps, cache_dir, use_gpu)
    matches_csv = work_dir / "matches.csv"
    write_csv(matches, matches_csv)
    raw_segments = build_segments(matches)
    if not raw_segments:
        raise RuntimeError("no matched segments found")
    raw_segments_json = work_dir / "raw_segments.json"
    raw_segments_json.write_text(
        json.dumps([asdict(s) | {"frame_count": s.frame_count} for s in raw_segments], indent=2, ensure_ascii=False)
    )
    raw_keys = {
        (segment.viral_start, segment.viral_end, segment.source_start, segment.source_end)
        for segment in raw_segments
    }
    segments = fill_gaps_by_extending_previous(raw_segments)
    match_params_json = work_dir / "match_params.json"
    match_params_json.write_text(json.dumps({
        "chunk_seconds": CHUNK_SECONDS,
        "crop_step": CROP_STEP,
        "feature_size": FEATURE_SIZE,
        "score_percentile": SCORE_PERCENTILE,
        "min_frames": MIN_FRAMES,
        "min_segment_frames": MIN_SEGMENT_FRAMES,
        "short_segment_frames": SHORT_SEGMENT_FRAMES,
        "tiny_segment_frames": TINY_SEGMENT_FRAMES,
        "bad_short_segment_score": BAD_SHORT_SEGMENT_SCORE,
        "bad_segment_score": BAD_SEGMENT_SCORE,
        "offset_tolerance": OFFSET_TOLERANCE,
        "crop_tolerance": CROP_TOLERANCE,
        "short_offset_tolerance": SHORT_OFFSET_TOLERANCE,
        "candidate_top_k": CANDIDATE_TOP_K,
        "max_candidates_per_frame": MAX_CANDIDATES_PER_FRAME,
        "use_gpu": use_gpu,
    }, indent=2, ensure_ascii=False))

    frame_matches = [
        legacy_segment_match(
            segment,
            index=index,
            kind="matched"
            if (segment.viral_start, segment.viral_end, segment.source_start, segment.source_end) in raw_keys
            else "gap_fill",
        )
        for index, segment in enumerate(segments, start=1)
    ]
    payload = build_frame_match_payload(
        node_type="VideoMatch",
        engine="legacy",
        viral_video=video_metadata(
            viral_path,
            fps=viral_fps,
            frame_count=viral_frames,
            width=viral_width,
            height=viral_height,
        ),
        source_video=video_metadata(
            source_path,
            fps=source_fps,
            frame_count=source_frames,
            width=source_width,
            height=source_height,
        ),
        matches=frame_matches,
        params={"use_gpu": use_gpu},
        artifacts={
            "matches_csv": str(matches_csv),
            "raw_segments_json": str(raw_segments_json),
            "match_params_json": str(match_params_json),
        },
    )
    segments_json = work_dir / "segments.json"
    segments_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    log(f"segments: {len(segments)}, frames: {sum(s.frame_count for s in segments)}")
    log("done")

    summary = {
        "segment_count": len(segments),
        "segment_frames": sum(s.frame_count for s in segments),
        "viral_frames": viral_frames,
        "output_dir": str(output_dir),
        "viral": str(viral_path),
        "source": str(source_path),
        "source_cache": str(cache_dir),
        "segments": str(segments_json),
        "matches": str(matches_csv),
        "use_gpu": use_gpu,
    }
    (work_dir / "verify_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def match_video(viral_path: str | Path, source_path: str | Path, output_dir: str | Path | None = None, use_gpu: bool = False) -> dict[str, object]:
    viral_path = Path(viral_path).expanduser().resolve()
    source_path = Path(source_path).expanduser().resolve()
    base_dir = Path.cwd()
    output_dir = Path(output_dir).expanduser().resolve() if output_dir else run_dir(viral_path, base_dir)
    work_dir = output_dir / "work"
    shots_dir = work_dir / "shots"
    output_video = output_dir / "final.mp4"
    output_html = output_dir / "review.html"
    work_dir.mkdir(parents=True, exist_ok=True)

    source_fps = fps(source_path)
    viral_fps = fps(viral_path)
    log(f"viral: {viral_path}")
    log(f"source: {source_path}")
    log(f"output: {output_dir}")
    log(f"fps: viral={viral_fps:.3f}, source={source_fps:.3f}")
    use_gpu = use_gpu and gpu_available()
    cache_dir = gpu_source_cache_dir(source_path, base_dir) if use_gpu else source_cache_dir(source_path, base_dir)
    log(f"source cache: {cache_dir}")
    log(f"gpu enabled: {use_gpu}")

    matches = find_matches(viral_path, source_path, source_fps, cache_dir, use_gpu)
    write_csv(matches, work_dir / "matches.csv")
    segments = build_segments(matches)
    if not segments:
        raise RuntimeError("no matched segments found")
    (work_dir / "raw_segments.json").write_text(json.dumps([asdict(s) | {"frame_count": s.frame_count} for s in segments], indent=2, ensure_ascii=False))
    segments = fill_gaps_by_extending_previous(segments)
    (work_dir / "segments.json").write_text(json.dumps([asdict(s) | {"frame_count": s.frame_count} for s in segments], indent=2, ensure_ascii=False))
    (work_dir / "match_params.json").write_text(json.dumps({
        "chunk_seconds": CHUNK_SECONDS,
        "crop_step": CROP_STEP,
        "feature_size": FEATURE_SIZE,
        "score_percentile": SCORE_PERCENTILE,
        "min_frames": MIN_FRAMES,
        "min_segment_frames": MIN_SEGMENT_FRAMES,
        "short_segment_frames": SHORT_SEGMENT_FRAMES,
        "tiny_segment_frames": TINY_SEGMENT_FRAMES,
        "bad_short_segment_score": BAD_SHORT_SEGMENT_SCORE,
        "bad_segment_score": BAD_SEGMENT_SCORE,
        "offset_tolerance": OFFSET_TOLERANCE,
        "crop_tolerance": CROP_TOLERANCE,
        "short_offset_tolerance": SHORT_OFFSET_TOLERANCE,
        "candidate_top_k": CANDIDATE_TOP_K,
        "max_candidates_per_frame": MAX_CANDIDATES_PER_FRAME,
        "use_gpu": use_gpu,
    }, indent=2, ensure_ascii=False))
    log(f"segments: {len(segments)}, frames: {sum(s.frame_count for s in segments)}")

    cut_segments(source_path, segments, source_fps, shots_dir)
    concat(shots_dir, len(segments), work_dir, output_video)
    shutil.rmtree(shots_dir)
    write_html(viral_path, output_video, output_html, segments)

    summary = {
        "segment_count": len(segments),
        "segment_frames": sum(s.frame_count for s in segments),
        "viral_frames": frame_count(viral_path, viral_fps),
        "matched_frames": frame_count(output_video, source_fps),
        "output_video": str(output_video),
        "output_html": str(output_html),
        "output_dir": str(output_dir),
        "viral": str(viral_path),
        "source": str(source_path),
        "source_cache": str(cache_dir),
        "segments": str(work_dir / "segments.json"),
        "matches": str(work_dir / "matches.csv"),
        "use_gpu": use_gpu,
    }
    (work_dir / "verify_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    log("done")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Match/cut a viral video from a source video.")
    parser.add_argument("viral_path", type=Path, help="爆款视频 path")
    parser.add_argument("source_path", type=Path, help="原视频 path")
    parser.add_argument("--gpu", action="store_true", help="使用 CUDA 加速候选搜索")
    args = parser.parse_args()
    print(json.dumps(match_video(args.viral_path, args.source_path, use_gpu=args.gpu), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
