import pytest

from app.copied.srt_llm_rewriter import GeminiSrtRewriter, SrtSegment, parse_json_array_response


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
