import json
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.copied import match_tuil
from app.copied.srt_llm_rewriter import GeminiSrtRewriter
from app.copied.tts_srt_extractor import extract_tts_srt
from app.jianying import create_jianying_draft


@dataclass(frozen=True)
class HotCopyInputs:
    viral_video: str | Path
    source_movie: str | Path
    output_dir: str | Path
    rewrite_notes: str = ""


def parse_srt_time(value: str) -> int:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def srt_entries(path: str | Path) -> list[dict[str, Any]]:
    entries = []
    text = Path(path).read_text("utf-8").strip()
    if not text:
        return entries
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [part.strip() for part in lines[1].split("-->")]
        entries.append(
            {
                "index": int(lines[0]),
                "start_ms": parse_srt_time(start),
                "end_ms": parse_srt_time(end),
                "text": " ".join(lines[2:]),
            }
        )
    return entries


def generate_minimax_audio(text: str, output_path: str | Path, settings: dict[str, Any]) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    api_key = settings.get("api_key")
    group_id = settings.get("group_id")
    if not api_key or not group_id:
        raise ValueError("missing Minimax api_key or group_id")

    url = f"{settings['base_url'].rstrip('/')}/v1/t2a_v2?GroupId={group_id}"
    body = {
        "model": settings["model"],
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": settings["voice_id"],
            "speed": settings["speed"],
            "vol": settings["volume"],
            "pitch": settings["pitch"],
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": settings["audio_format"],
            "channel": 1,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                data = json.loads(response.read())
            break
        except (urllib.error.URLError, ssl.SSLError) as exc:
            if attempt == 2:
                raise RuntimeError(f"Minimax request failed after 3 attempts: {exc}") from exc
            time.sleep(2 * (attempt + 1))

    audio_hex = data.get("data", {}).get("audio")
    if not audio_hex:
        raise RuntimeError(f"Minimax did not return audio: {data}")
    output_path.write_bytes(bytes.fromhex(audio_hex))
    return output_path


def compose_video(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    settings: dict[str, Any],
    tts_entries: list[dict[str, Any]] | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duck_filters = ",".join(
        f"volume=enable='between(t,{entry['start_ms'] / 1000:.3f},{entry['end_ms'] / 1000:.3f})':volume=0.2"
        for entry in (tts_entries or [])
    )
    duck_filters = duck_filters or "anull"
    filter_complex = (
        f"[0:a:0]{duck_filters}[bg];"
        "[bg][1:a:0]amix=inputs=2:duration=first:dropout_transition=0,aformat=channel_layouts=stereo[aout]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-filter_complex",
            filter_complex,
            "-map",
            "[aout]",
            "-c:v",
            settings["video_codec"],
            "-c:a",
            settings["audio_codec"],
            "-shortest",
            str(output_path),
        ],
        check=True,
    )
    return output_path


def compose_timed_audio(entries: list[dict[str, Any]], audio_paths: list[Path], output_path: str | Path) -> Path:
    if not entries:
        raise ValueError("rewritten SRT has no subtitle entries")
    if len(entries) != len(audio_paths):
        raise ValueError("subtitle entry count does not match generated audio count")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for audio_path in audio_paths:
        cmd += ["-i", str(audio_path)]
    filter_parts = []
    delayed = []
    total_ms = max(entry["end_ms"] for entry in entries) if entries else 0
    for index, entry in enumerate(entries):
        label = f"a{index}"
        filter_parts.append(f"[{index}:a]adelay={entry['start_ms']}|{entry['start_ms']},apad=whole_dur={total_ms / 1000:.3f}[{label}]")
        delayed.append(f"[{label}]")
    filter_parts.append(f"{''.join(delayed)}amix=inputs={len(delayed)}:normalize=0[out]")
    cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[out]", "-c:a", "aac", str(output_path)]
    subprocess.run(cmd, check=True)
    return output_path


def run_pipeline(inputs: HotCopyInputs, settings: dict[str, Any], progress: Callable[[str], None] | None = None) -> dict[str, str]:
    progress = progress or (lambda message: None)
    output_dir = Path(inputs.output_dir or settings["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    progress("TTS分离")
    tts_dir = output_dir / "tts"
    tts = extract_tts_srt(
        inputs.viral_video,
        api_key=settings["llm"]["api_key"],
        gemini_model=settings["llm"]["model"],
        base_url=settings["llm"]["base_url"],
        whisper_model=Path(settings["paths"]["whisper_model"]),
        vad_model=Path(settings["paths"]["vad_model"]),
        vad_threshold=settings["vad"]["threshold"],
        min_speech_ms=settings["vad"]["min_speech_ms"],
        min_silence_ms=settings["vad"]["min_silence_ms"],
        min_word_overlap=settings["tts_extract"]["min_word_overlap"],
        refresh_gemini=settings["tts_extract"]["refresh_gemini"],
        output_dir=tts_dir,
    )
    progress("文案改写")
    rewritten_srt = output_dir / "rewritten.srt"
    style = settings["rewrite"]["style"]
    if inputs.rewrite_notes:
        style = f"{style}; {inputs.rewrite_notes}"
    GeminiSrtRewriter(
        api_key=settings["llm"]["api_key"],
        model=settings["llm"]["model"],
        base_url=settings["llm"]["base_url"],
    ).rewrite_file(
        tts.final_srt_path,
        rewritten_srt,
        settings["rewrite"]["target_language"],
        style,
        settings["rewrite"]["max_segment_seconds"],
        settings["rewrite"]["max_gap_ms"],
    )
    progress("镜头匹配")
    match = match_tuil.match_video(
        inputs.viral_video,
        inputs.source_movie,
        output_dir / "match",
        use_gpu=settings["video_match"].get("gpu_enabled", False),
    )
    progress("Minimax生成音频")
    entries = srt_entries(rewritten_srt)
    segment_audio_dir = output_dir / "audio_segments"
    segment_audio_dir.mkdir(parents=True, exist_ok=True)
    segment_audio_paths = []
    for index, entry in enumerate(entries, 1):
        progress(f"Minimax生成音频 {index}/{len(entries)}")
        segment_audio_paths.append(
            generate_minimax_audio(entry["text"], segment_audio_dir / f"{entry['index']:04d}.{settings['minimax']['audio_format']}", settings["minimax"])
        )
    audio_path = compose_timed_audio(entries, segment_audio_paths, output_dir / "voice_timeline.m4a")
    progress("内容拼接")
    final_video = compose_video(match["output_video"], audio_path, output_dir / "final.mp4", settings["compose"], entries)
    progress("生成剪映草稿")
    draft_path = create_jianying_draft(final_video, inputs.viral_video)

    return {
        "tts_srt": str(tts.final_srt_path),
        "rewritten_srt": str(rewritten_srt),
        "matched_video": str(match["output_video"]),
        "audio": str(audio_path),
        "final_video": str(final_video),
        "jianying_draft": str(draft_path),
    }
