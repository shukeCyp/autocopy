from pathlib import Path

from app.copied.match_tuil import CandidateMatch, Match, Segment, build_segments, choose_temporal_matches, cut_segments, drop_bad_segments, fill_gaps_by_extending_previous, optimize_segment_boundaries, smooth_short_segments


def test_cut_segments_keeps_source_resolution(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)

    monkeypatch.setattr("app.copied.match_tuil.run", fake_run)

    cut_segments(
        Path("source.mkv"),
        [Segment(0, 9, 100, 109, 400, False, 1.0, 2.0)],
        25.0,
        tmp_path,
    )

    vf = calls[0][calls[0].index("-vf") + 1]
    assert "crop=" not in vf
    assert vf == "null"
    assert "-an" not in calls[0]


def test_cut_segments_preserves_flip_without_crop(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("app.copied.match_tuil.run", lambda cmd: calls.append(cmd))

    cut_segments(
        Path("source.mkv"),
        [Segment(0, 9, 100, 109, 400, True, 1.0, 2.0)],
        25.0,
        tmp_path,
    )

    vf = calls[0][calls[0].index("-vf") + 1]
    assert vf == "hflip"


def test_build_segments_drops_segments_shorter_than_12_frames():
    matches = [Match(i, 100 + i, 1.0, 400, False) for i in range(10)]

    assert build_segments(matches) == []


def test_choose_temporal_matches_prefers_continuous_path_over_single_better_jump():
    candidates = {
        0: [CandidateMatch(0, 100, 1.0, 400, False)],
        1: [
            CandidateMatch(1, 500, 0.1, 400, False),
            CandidateMatch(1, 101, 1.2, 400, False),
        ],
        2: [CandidateMatch(2, 102, 1.0, 400, False)],
    }

    matches = choose_temporal_matches(candidates)

    assert [match.source_frame for match in matches] == [100, 101, 102]


def test_fill_gaps_by_extending_previous_segment():
    segments = [
        Segment(0, 9, 100, 109, 400, False, 1.0, 2.0),
        Segment(15, 19, 300, 304, 400, False, 3.0, 4.0),
    ]

    filled = fill_gaps_by_extending_previous(segments)

    assert [(s.viral_start, s.viral_end, s.source_start, s.source_end) for s in filled] == [
        (0, 9, 100, 109),
        (10, 14, 110, 114),
        (15, 19, 300, 304),
    ]


def test_smooth_short_segments_bridges_short_timeline_jump():
    segments = [
        Segment(0, 39, 1000, 1039, 400, False, 6.0, 8.0),
        Segment(40, 64, 5000, 5024, 400, False, 14.0, 15.0),
        Segment(65, 100, 1065, 1100, 400, False, 6.0, 8.0),
    ]

    smoothed = smooth_short_segments(segments)

    assert len(smoothed) == 1
    assert smoothed[0].viral_start == 0
    assert smoothed[0].viral_end == 100
    assert smoothed[0].source_start == 1000
    assert smoothed[0].source_end == 1100


def test_drop_bad_segments_removes_short_high_score_jump():
    segments = [
        Segment(0, 39, 1000, 1039, 400, False, 6.0, 8.0),
        Segment(40, 64, 5000, 5024, 400, False, 14.0, 15.0),
        Segment(65, 100, 2000, 2035, 400, False, 6.0, 8.0),
    ]

    clean = drop_bad_segments(segments)

    assert [segment.viral_start for segment in clean] == [0, 65]


def test_optimize_segment_boundaries_fills_small_continuous_gap():
    segments = [
        Segment(0, 39, 1000, 1039, 400, False, 6.0, 8.0),
        Segment(45, 80, 1045, 1080, 400, False, 6.0, 8.0),
    ]

    optimized = optimize_segment_boundaries(segments)

    assert len(optimized) == 1
    assert optimized[0].viral_start == 0
    assert optimized[0].viral_end == 80
    assert optimized[0].source_start == 1000
    assert optimized[0].source_end == 1080
