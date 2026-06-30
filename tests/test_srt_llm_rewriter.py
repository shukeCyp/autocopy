import json

import pytest

from app.copied.srt_llm_rewriter import GeminiSrtRewriter, SrtSegment, parse_json_array_response, parse_srt


def test_parse_json_array_response_extracts_array_from_text():
    assert parse_json_array_response('result:\n[{"id": 1, "text": "ok"}]') == [{"id": 1, "text": "ok"}]


def test_parse_json_array_response_rejects_non_array():
    with pytest.raises(ValueError):
        parse_json_array_response('{"id": 1}')


def test_rewrite_batch_falls_back_to_original_text(monkeypatch):
    monkeypatch.setattr("app.copied.srt_llm_rewriter.gemini_text", lambda *args: "")
    monkeypatch.setattr("app.copied.srt_llm_rewriter.time.sleep", lambda seconds: None)
    rewriter = GeminiSrtRewriter(api_key="key")
    segments = [SrtSegment(1, "00:00:00,000 --> 00:00:01,000", "original", 1000)]

    assert rewriter._rewrite_segment_batch(segments, "Chinese", "style") == ["original"]


def test_rewrite_file_merges_timing_and_reprompts_overlong_text(monkeypatch, tmp_path):
    input_srt = tmp_path / "input.srt"
    input_srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nfirst line\n\n"
        "2\n00:00:01,200 --> 00:00:02,000\nsecond line\n\n"
        "3\n00:00:04,000 --> 00:00:05,000\nthird line\n",
        encoding="utf-8",
    )
    output_srt = tmp_path / "rewritten.srt"
    calls = []
    responses = [
        [
            {"id": 1, "text": "这是一个非常非常非常非常非常非常非常非常长的洗稿句子"},
            {"id": 2, "text": "第三句"},
        ],
        [
            {"id": 1, "text": "短句改写"},
        ],
    ]

    def fake_gemini_text(prompt, *args):
        calls.append(prompt)
        return json.dumps(responses.pop(0), ensure_ascii=False)

    monkeypatch.setattr("app.copied.srt_llm_rewriter.gemini_text", fake_gemini_text)
    rewriter = GeminiSrtRewriter(api_key="key")

    rewriter.rewrite_file(
        input_srt,
        output_srt,
        target_language="Chinese",
        style="short-video narration",
        max_segment_seconds=30,
        max_gap_ms=700,
    )

    rewritten = parse_srt(output_srt)
    assert [(entry.timing, entry.text) for entry in rewritten] == [
        ("00:00:00,000 --> 00:00:02,000", "短句改写"),
        ("00:00:04,000 --> 00:00:05,000", "第三句"),
    ]
    assert len(calls) == 2
    assert "max_reading_units" in calls[0]
    assert "Shorten these rewritten SRT narration segments" in calls[1]
