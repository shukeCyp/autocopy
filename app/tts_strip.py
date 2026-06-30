from __future__ import annotations

import json
import os
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.model_cache import model_cache_path

from app.copied.tts_srt_extractor import parse_srt, run, vad_segments, write_srt


PYANNOTE_EMBEDDING_MODEL = "pyannote/wespeaker-voxceleb-resnet34-LM"


@dataclass(frozen=True)
class SpeechSegmentsResult:
    segments_dir: Path
    segments_json: Path
    segments: list[dict[str, Any]]


@dataclass(frozen=True)
class DominantSpeakerResult:
    segments_json: Path
    report_json: Path
    speaker_id: int
    segments: list[dict[str, Any]]


@dataclass(frozen=True)
class SegmentAsrResult:
    srt_path: Path
    entries: list[tuple[int, int, str]]


def split_speech_segments(
    audio_path: str | Path,
    *,
    vad_model: str | Path,
    output_dir: str | Path,
    threshold: float = 0.25,
    min_speech_ms: int = 10,
    min_silence_ms: int = 50,
) -> SpeechSegmentsResult:
    audio = Path(audio_path)
    if not audio.is_file():
        raise FileNotFoundError(audio)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    segments = []
    for index, (start, end) in enumerate(
        vad_segments(audio, vad_model, threshold, min_speech_ms, min_silence_ms),
        1,
    ):
        segment_path = output / f"segment_{index:04d}.wav"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                str(audio),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(segment_path),
            ],
            quiet=True,
        )
        start_ms = int(round(start * 1000))
        end_ms = int(round(end * 1000))
        segments.append(
            {
                "index": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
                "audio_path": str(segment_path),
            }
        )

    segments_json = output / "segments.json"
    segments_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
    return SpeechSegmentsResult(output, segments_json, segments)


def voice_embedding(
    audio_path: str | Path,
    *,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> np.ndarray:
    inference = _get_pyannote_inference(model_source, _resolve_hf_token(hf_token))
    embedding = _to_numpy_vector(inference(str(audio_path)))
    if embedding.size == 0:
        raise ValueError(f"empty speaker embedding: {audio_path}")
    return _normalize(embedding)


def select_dominant_speaker(
    segments_json: str | Path,
    *,
    output_json: str | Path,
    report_json: str | Path,
    similarity_threshold: float = 0.82,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> DominantSpeakerResult:
    segments = json.loads(Path(segments_json).read_text())
    clusters: list[dict[str, Any]] = []

    for segment in segments:
        embedding = voice_embedding(
            segment["audio_path"],
            hf_token=hf_token,
            model_source=model_source,
        )
        match_index = _best_cluster_index(clusters, embedding, similarity_threshold)
        if match_index is None:
            clusters.append(
                {
                    "speaker_id": len(clusters),
                    "embedding": embedding,
                    "segments": [segment],
                    "total_duration_ms": int(segment.get("duration_ms", 0)),
                }
            )
            continue

        cluster = clusters[match_index]
        cluster["segments"].append(segment)
        cluster["total_duration_ms"] += int(segment.get("duration_ms", 0))
        cluster["embedding"] = _normalize(
            (cluster["embedding"] * (len(cluster["segments"]) - 1) + embedding)
            / len(cluster["segments"])
        )

    if not clusters:
        raise ValueError("no speech segments found")

    dominant = max(clusters, key=lambda cluster: cluster["total_duration_ms"])
    selected = sorted(dominant["segments"], key=lambda segment: segment["start_ms"])

    output_path = Path(output_json)
    report_path = Path(report_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2))
    report = {
        "dominant_speaker_id": dominant["speaker_id"],
        "speakers": [
            {
                "speaker_id": cluster["speaker_id"],
                "segment_count": len(cluster["segments"]),
                "total_duration_ms": cluster["total_duration_ms"],
                "segments": [segment["index"] for segment in cluster["segments"]],
            }
            for cluster in clusters
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return DominantSpeakerResult(output_path, report_path, dominant["speaker_id"], selected)


def transcribe_segments_to_srt(
    segments_json: str | Path,
    *,
    whisper_model: str | Path,
    output_srt: str | Path,
    work_dir: str | Path,
    language: str = "en",
    prompt: str = "",
    speaker_filter: bool = False,
    speaker_threshold: float = 0.3,
    timing_offset_ms: int = 0,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> SegmentAsrResult:
    segments = json.loads(Path(segments_json).read_text())
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[int, int, str]] = []
    entry_records: list[dict[str, Any]] = []

    for segment in segments:
        audio_path = Path(segment["audio_path"])
        out_base = work / f"asr_{int(segment['index']):04d}"
        cmd = [
            "whisper-cli",
            "-m",
            str(whisper_model),
            "-l",
            language,
            "-np",
            "-ml",
            "30",
            "-sow",
            "-osrt",
            "-of",
            str(out_base),
        ]
        if prompt:
            cmd += ["--prompt", prompt[:800]]
        cmd.append(str(audio_path))
        run(cmd, quiet=True)

        offset = int(segment["start_ms"])
        for start, end, text in parse_srt(out_base.with_suffix(".srt")):
            absolute = (start + offset, end + offset, text)
            entries.append(absolute)
            entry_records.append(
                {
                    "entry": absolute,
                    "audio_path": audio_path,
                    "local_start_ms": start,
                    "local_end_ms": end,
                }
            )

    if speaker_filter:
        entries = _filter_asr_entries_by_dominant_speaker(
            entry_records,
            output_dir=work / "speaker_filter",
            similarity_threshold=speaker_threshold,
            hf_token=hf_token,
            model_source=model_source,
        )

    if timing_offset_ms:
        entries = [
            (max(0, start + timing_offset_ms), max(0, end + timing_offset_ms), text)
            for start, end, text in entries
        ]

    srt_path = Path(output_srt)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    write_srt(entries, srt_path)
    return SegmentAsrResult(srt_path, entries)


def _filter_asr_entries_by_dominant_speaker(
    records: list[dict[str, Any]],
    *,
    output_dir: str | Path,
    similarity_threshold: float,
    hf_token: str | None,
    model_source: str,
) -> list[tuple[int, int, str]]:
    if len(records) <= 1:
        return [record["entry"] for record in records]

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    clusters: list[dict[str, Any]] = []
    clustered_records: list[dict[str, Any]] = []

    for index, record in enumerate(records, 1):
        start = int(record["local_start_ms"])
        end = int(record["local_end_ms"])
        duration = max(0, end - start)
        if duration < 300:
            continue

        line_audio = output / f"line_{index:04d}.wav"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start / 1000:.3f}",
                "-to",
                f"{end / 1000:.3f}",
                "-i",
                str(record["audio_path"]),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(line_audio),
            ],
            quiet=True,
        )

        embedding = voice_embedding(
            line_audio,
            hf_token=hf_token,
            model_source=model_source,
        )
        match_index = _best_cluster_index(clusters, embedding, similarity_threshold)
        cluster_record = {**record, "duration_ms": duration}
        if match_index is None:
            clusters.append(
                {
                    "speaker_id": len(clusters),
                    "embedding": embedding,
                    "records": [cluster_record],
                    "total_duration_ms": duration,
                }
            )
        else:
            cluster = clusters[match_index]
            cluster["records"].append(cluster_record)
            cluster["total_duration_ms"] += duration
            cluster["embedding"] = _normalize(
                (cluster["embedding"] * (len(cluster["records"]) - 1) + embedding)
                / len(cluster["records"])
            )
        clustered_records.append(cluster_record)

    if not clusters:
        return [record["entry"] for record in records]

    dominant = max(clusters, key=lambda cluster: cluster["total_duration_ms"])
    selected_ids = {id(record) for record in dominant["records"]}
    return [
        record["entry"]
        for record in clustered_records
        if id(record) in selected_ids
    ]


def _resolve_hf_token(hf_token: str | None) -> str | None:
    token = (hf_token or "").strip()
    return token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")


@lru_cache(maxsize=4)
def _get_pyannote_inference(
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
    hf_token: str | None = None,
    savedir: str | None = None,
):
    try:
        from pyannote.audio import Inference, Model
    except ImportError as exc:
        raise RuntimeError("pyannote.audio is required for speaker embedding") from exc

    try:
        model = Model.from_pretrained(
            model_source,
            token=hf_token,
            cache_dir=savedir or str(model_cache_path("pyannote")),
        )
        if model is None:
            raise RuntimeError("Pyannote returned no model")
    except Exception as exc:
        raise RuntimeError(
            f"failed to load Pyannote speaker embedding model '{model_source}'. "
            "Use the default pyannote/wespeaker-voxceleb-resnet34-LM model, "
            "or provide hf_token/set HF_TOKEN after accepting access for gated Pyannote models."
        ) from exc
    return Inference(model, window="whole")


def _to_numpy_vector(value: Any) -> np.ndarray:
    if hasattr(value, "data"):
        value = value.data
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    vector = np.asarray(value, dtype=np.float32)
    while vector.ndim > 1:
        vector = vector.mean(axis=0)
    return vector


def _best_cluster_index(
    clusters: list[dict[str, Any]],
    embedding: np.ndarray,
    threshold: float,
) -> int | None:
    if not clusters:
        return None
    similarities = [
        float(np.dot(cluster["embedding"], embedding))
        for cluster in clusters
    ]
    best_index = int(np.argmax(similarities))
    return best_index if similarities[best_index] >= threshold else None


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm
