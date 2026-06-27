#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SrtEntry:
    index: int
    timing: str
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class SrtSegment:
    index: int
    timing: str
    text: str
    duration_ms: int


def clean_response(text):
    text = re.sub(r"```(?:json)?|```", "", text, flags=re.I).strip()
    return text


def parse_json_array_response(text):
    text = clean_response(text or "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON array")
    return data


def parse_time(value):
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def format_time(ms):
    h, rem = divmod(max(0, int(ms)), 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path):
    entries = []
    text = Path(path).read_text().strip()
    if not text:
        return entries
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            start, end = [part.strip() for part in lines[1].split("-->")]
            entries.append(SrtEntry(int(lines[0]), lines[1], " ".join(lines[2:]), parse_time(start), parse_time(end)))
    return entries


def clean_segment_text(text):
    text = re.sub(r"^\s*(?:was|you|yeah|yes|no|okay|ok|um|uh|oh)\??\.?\s+", "", text, flags=re.I)
    text = re.sub(r"\b(\w+)\.\s+\1\b", r"\1", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def group_by_vad_duration(entries, max_segment_seconds=30, max_gap_ms=700):
    segments = []
    current = []
    for entry in entries:
        if current:
            too_long = entry.end_ms - current[0].start_ms > max_segment_seconds * 1000
            too_far = entry.start_ms - current[-1].end_ms > max_gap_ms
            if too_long or too_far:
                segments.append(make_segment(len(segments) + 1, current))
                current = []
        current.append(entry)
    if current:
        segments.append(make_segment(len(segments) + 1, current))
    return segments


def make_segment(index, entries):
    start, end = entries[0].start_ms, entries[-1].end_ms
    return SrtSegment(
        index=index,
        timing=f"{format_time(start)} --> {format_time(end)}",
        text=clean_segment_text(" ".join(e.text for e in entries)),
        duration_ms=end - start,
    )


def write_srt(entries, texts, path):
    blocks = []
    for entry, text in zip(entries, texts):
        blocks.append(f"{entry.index}\n{entry.timing}\n{text.strip()}\n")
    Path(path).write_text("\n".join(blocks))


def gemini_text(prompt, api_key, model, base_url):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
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
    return clean_response(data["candidates"][0]["content"]["parts"][0]["text"])


class GeminiSrtRewriter:
    def __init__(self, api_key=None, model="gemini-3.5-flash", base_url="https://yunwu.ai"):
        self.api_key = api_key or os.environ.get("YUNWU_API_KEY")
        if not self.api_key:
            raise ValueError("missing api_key or YUNWU_API_KEY")
        self.model = model
        self.base_url = base_url

    def rewrite_file(
        self,
        input_srt,
        output_srt=None,
        target_language="Chinese",
        style="localized short-video crime recap",
        max_segment_seconds=30,
        max_gap_ms=700,
    ):
        entries = parse_srt(input_srt)
        output_srt = Path(output_srt) if output_srt else Path(input_srt).with_suffix(".rewritten.srt")
        segments = group_by_vad_duration(entries, max_segment_seconds, max_gap_ms)
        rewritten = self.rewrite_segments(segments, target_language, style)
        write_srt(segments, rewritten, output_srt)
        return output_srt

    def rewrite_segments(self, segments, target_language, style, batch_size=12):
        result = []
        for i in range(0, len(segments), batch_size):
            result.extend(self._rewrite_segment_batch(segments[i:i + batch_size], target_language, style))
        return result

    def _rewrite_segment_batch(self, segments, target_language, style):
        payload = [
            {
                "id": s.index,
                "duration_seconds": round(s.duration_ms / 1000, 2),
                "source_word_count": len(re.findall(r"\S+", s.text)),
                "text": s.text,
            }
            for s in segments
        ]
        prompt = (
            f"Rewrite these SRT narration segments into {target_language}.\n"
            f"Style: {style}.\n"
            "Rules:\n"
            "- Return a JSON array only, same length and same ids.\n"
            "- Each output item must be one segment-level subtitle text, not line-by-line fragments.\n"
            "- Keep each segment close to the source length and readable within duration_seconds.\n"
            "- Preserve suspense, pacing, and short-video narration rhythm.\n"
            "- Localize naturally for the target audience; avoid literal translation.\n"
            "- Localize roles, institutions, idioms, and titles. For example, Chinese '监狱长' should become the natural local equivalent such as 'warden' in English, not a stiff literal phrase.\n"
            "- Do not include timestamps, markdown, comments, or explanations.\n\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        data = self._json_batch(prompt, segments)
        by_id = {int(item["id"]): str(item["text"]).strip() for item in data}
        return [by_id.get(s.index, s.text) for s in segments]

    def rewrite_entries(self, entries, target_language, style, batch_size=40):
        result = []
        for i in range(0, len(entries), batch_size):
            result.extend(self._rewrite_batch(entries[i:i + batch_size], target_language, style))
        return result

    def _rewrite_batch(self, entries, target_language, style):
        payload = [{"id": e.index, "text": e.text, "duration_hint": e.timing} for e in entries]
        prompt = (
            f"Rewrite these SRT subtitle texts into {target_language}.\n"
            f"Style: {style}.\n"
            "Rules:\n"
            "- Return a JSON array only, same length and same ids.\n"
            "- Keep each line close to the original length and speaking duration.\n"
            "- Preserve meaning, suspense, pacing, and recap narration style.\n"
            "- Localize idioms, job titles, institutions, and names naturally for the target audience.\n"
            "- Do not translate literally when it sounds foreign or awkward.\n"
            "- Example warning: do not translate Chinese '监狱长' mechanically as a strange literal phrase; use the natural local equivalent such as 'warden' in English.\n"
            "- No timestamps, no explanations.\n\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        data = self._json_batch(prompt, entries)
        by_id = {int(item["id"]): str(item["text"]).strip() for item in data}
        return [by_id.get(e.index, e.text) for e in entries]

    def _json_batch(self, prompt, originals, attempts=3):
        last_error = None
        for attempt in range(attempts):
            try:
                data = parse_json_array_response(gemini_text(prompt, self.api_key, self.model, self.base_url))
                if len(data) == len(originals):
                    return data
                last_error = ValueError(f"LLM returned {len(data)} items, expected {len(originals)}")
            except Exception as error:
                last_error = error
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
        print(f"rewrite fallback: {last_error}", flush=True)
        return [{"id": item.index, "text": item.text} for item in originals]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_srt", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--language", default="Chinese")
    ap.add_argument("--style", default="localized short-video crime recap")
    ap.add_argument("--max-segment-seconds", type=float, default=30)
    ap.add_argument("--max-gap-ms", type=int, default=700)
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--base-url", default="https://yunwu.ai")
    args = ap.parse_args()

    out = GeminiSrtRewriter(model=args.model, base_url=args.base_url).rewrite_file(
        args.input_srt,
        args.output,
        args.language,
        args.style,
        args.max_segment_seconds,
        args.max_gap_ms,
    )
    print(out)


if __name__ == "__main__":
    main()
