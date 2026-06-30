#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TtsSrtResult:
    script_path: Path
    full_asr_srt_path: Path
    final_srt_path: Path


def run(cmd, quiet=False):
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE} if quiet else {}
    subprocess.run(cmd, check=True, **kwargs)


def extract_audio(video, wav):
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", str(wav),
    ])


def clean_text(text):
    text = re.sub(r"```(?:text|json)?|```", "", text, flags=re.I).strip()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def gemini_audio_text(wav, api_key, model, base_url):
    prompt = (
        "This audio contains drama dialogue plus an English recap/narration TTS voice. "
        "Transcribe only the recap/narration TTS script, in order, verbatim. "
        "Do not paraphrase, correct grammar, normalize names, or add missing words. "
        "Do not include character dialogue, sound effects, music descriptions, timestamps, bullets, or explanations. "
        "Return plain text only."
    )
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "audio/wav",
                        "data": base64.b64encode(Path(wav).read_bytes()).decode(),
                    }
                },
            ],
        }],
        "generationConfig": {"temperature": 0},
    }
    url = (
        f"{base_url.rstrip('/')}/v1beta/models/{urllib.parse.quote(model)}"
        f":generateContent?key={urllib.parse.quote(api_key)}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    return clean_text(data["candidates"][0]["content"]["parts"][0]["text"])


def transcribe_json(wav, model, out_base, prompt):
    model_name = Path(model).name
    if "large-v3-turbo" in model_name:
        dtw_model = "large.v3.turbo"
    elif "large-v3" in model_name:
        dtw_model = "large.v3"
    elif "tiny" in model_name:
        dtw_model = "tiny.en"
    else:
        dtw_model = "small.en"
    cmd = [
        "whisper-cli", "-m", str(model), "-l", "en", "-np",
        "-ml", "30", "-sow", "-oj", "-osrt", "-of", str(out_base),
        "--dtw", dtw_model, "--prompt", prompt[:800], str(wav),
    ]
    run(cmd, quiet=True)
    return json.loads(out_base.with_suffix(".json").read_text()).get("transcription", [])


def parse_srt(path):
    path = Path(path)
    if not path.exists() or not path.read_text().strip():
        return []
    entries = []
    for block in re.split(r"\n\s*\n", path.read_text().strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [part.strip() for part in lines[1].split("-->")]
        entries.append((parse_srt_time(start), parse_srt_time(end), " ".join(lines[2:])))
    return entries


def parse_srt_time(value):
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def vad_segments(wav, vad_model, threshold=0.25, min_speech_ms=10, min_silence_ms=50):
    cp = subprocess.run([
        "whisper-vad-speech-segments", "-np",
        "-vm", str(vad_model),
        "-vt", str(threshold),
        "--vad-min-speech-duration-ms", str(min_speech_ms),
        "-vsd", str(min_silence_ms),
        "-f", str(wav),
    ], check=True, capture_output=True, text=True)
    segments = []
    for line in cp.stdout.splitlines():
        match = re.search(r"start = ([0-9.]+), end = ([0-9.]+)", line)
        if match:
            # whisper.cpp VAD prints 10 ms ticks.
            segments.append((float(match.group(1)) / 100, float(match.group(2)) / 100))
    return segments


def transcribe_vad_entries(wav, model, vad_model, prompt, work, threshold=0.25, min_speech_ms=10, min_silence_ms=50):
    entries = []
    for i, (start, end) in enumerate(vad_segments(wav, vad_model, threshold, min_speech_ms, min_silence_ms)):
        piece = work / f"vad_{i:04d}.wav"
        out_base = work / f"vad_{i:04d}"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-i", str(wav), "-ar", "16000", "-ac", "1", str(piece),
        ], quiet=True)
        run([
            "whisper-cli", "-m", str(model), "-l", "en", "-np",
            "-ml", "30", "-sow", "-osrt", "-of", str(out_base),
            "--prompt", prompt[:800], str(piece),
        ], quiet=True)
        offset = int(start * 1000)
        entries.extend((s + offset, e + offset, text) for s, e, text in parse_srt(out_base.with_suffix(".srt")))
    return entries


def srt_time(ms):
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def norm_words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def clean_tts_text(text):
    text = re.sub(r"^\s*(?:was|you|yeah|yes|no|okay|ok|um|uh|oh)\??\.?\s+", "", text, flags=re.I)
    text = re.sub(r"\b(\w+)\.\s+\1\b", r"\1", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def transcript_entries(transcript):
    entries = []
    for seg in transcript:
        offsets = seg.get("offsets", {})
        text = seg.get("text", "").strip()
        if text:
            entries.append((int(offsets.get("from", 0)), int(offsets.get("to", 0)), text))
    return entries


def filter_entries(entries, script, min_word_overlap=0.85, min_word_density=1.3):
    script_words = set(norm_words(script))
    kept = []
    for start, end, text in entries:
        text = clean_tts_text(text)
        words = norm_words(text)
        if len(words) < 2:
            continue
        overlap = sum(1 for word in words if word in script_words) / len(words)
        density = len(words) / max(0.001, (end - start) / 1000)
        if overlap >= min_word_overlap and density >= min_word_density:
            kept.append((start, end, text))
    return kept


def write_srt(entries, path):
    blocks = []
    for i, (start, end, text) in enumerate(entries, 1):
        blocks.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{text.strip()}\n")
    path.write_text("\n".join(blocks))


def extract_tts_srt(
    video_path,
    *,
    api_key=None,
    gemini_model="gemini-3.5-flash",
    base_url="https://yunwu.ai",
    whisper_model=Path("model/ggml-large-v3-turbo.bin"),
    vad_model=Path("model/ggml-silero-v6.2.0.bin"),
    vad_threshold=0.25,
    min_speech_ms=10,
    min_silence_ms=50,
    min_word_overlap=0.85,
    refresh_gemini=False,
    output_dir=None,
):
    video = Path(video_path)
    api_key = api_key or os.environ.get("YUNWU_API_KEY")
    if not api_key:
        raise ValueError("missing api_key or YUNWU_API_KEY")

    output_dir = Path(output_dir) if output_dir else video.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / f"{video.stem}.gemini_tts.txt"
    full_srt_path = output_dir / f"{video.stem}.full_asr.srt"
    final_srt_path = output_dir / f"{video.stem}.final_tts.srt"

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        wav = work / "audio.wav"
        extract_audio(video, wav)
        if script_path.exists() and not refresh_gemini:
            script = script_path.read_text()
        else:
            script = gemini_audio_text(wav, api_key, gemini_model, base_url)
            script_path.write_text(script.strip() + "\n")
        if vad_model and Path(vad_model).exists():
            entries = transcribe_vad_entries(wav, whisper_model, Path(vad_model), script, work, vad_threshold, min_speech_ms, min_silence_ms)
        else:
            transcript = transcribe_json(wav, whisper_model, work / "whisper", script)
            entries = transcript_entries(transcript)

    write_srt(entries, full_srt_path)
    write_srt(filter_entries(entries, script, min_word_overlap), final_srt_path)
    return TtsSrtResult(script_path, full_srt_path, final_srt_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--gemini-model", default="gemini-3.5-flash")
    ap.add_argument("--base-url", default="https://yunwu.ai")
    ap.add_argument("--whisper-model", type=Path, default=Path("model/ggml-large-v3-turbo.bin"))
    ap.add_argument("--vad-model", type=Path, default=Path("model/ggml-silero-v6.2.0.bin"))
    ap.add_argument("--vad-threshold", type=float, default=0.25)
    ap.add_argument("--min-word-overlap", type=float, default=0.85)
    ap.add_argument("--refresh-gemini", action="store_true")
    args = ap.parse_args()

    result = extract_tts_srt(
        args.video,
        gemini_model=args.gemini_model,
        base_url=args.base_url,
        whisper_model=args.whisper_model,
        vad_model=args.vad_model,
        vad_threshold=args.vad_threshold,
        min_word_overlap=args.min_word_overlap,
        refresh_gemini=args.refresh_gemini,
    )
    print(f"Gemini文案: {result.script_path}")
    print(f"完整ASR: {result.full_asr_srt_path}")
    print(f"最终TTS SRT: {result.final_srt_path}")


if __name__ == "__main__":
    main()
