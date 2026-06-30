from app.frame_match import build_frame_match_payload, legacy_segment_match, video_metadata
from app.copied.match_tuil import Segment


def test_legacy_segment_match_uses_exclusive_frame_ranges():
    match = legacy_segment_match(
        Segment(
            viral_start=10,
            viral_end=19,
            source_start=110,
            source_end=119,
            crop_x=400,
            flipped=True,
            avg_score=5.5,
            max_score=7.25,
        ),
        index=1,
        kind="matched",
    )

    assert match["viral"] == {
        "start_frame": 10,
        "end_frame_exclusive": 20,
        "frame_count": 10,
    }
    assert match["source"] == {
        "start_frame": 110,
        "end_frame_exclusive": 120,
        "frame_count": 10,
    }
    assert match["mapping"]["source_per_viral"] == {"num": 10, "den": 10}
    assert match["transform"]["mirrored"] is True
    assert match["transform"]["crop"]["x"] == 400
    assert match["quality"]["primary"] == {
        "name": "legacy_avg_score",
        "value": 5.5,
        "higher_is_better": False,
    }


def test_frame_match_payload_contains_only_frame_ranges():
    payload = build_frame_match_payload(
        node_type="VideoMatch",
        engine="legacy",
        viral_video=video_metadata("/viral.mp4", fps=25.0, frame_count=100, width=1080, height=1920),
        source_video=video_metadata("/source.mp4", fps=24.0, frame_count=1000, width=1920, height=1080),
        matches=[
            legacy_segment_match(
                Segment(10, 19, 110, 119, 400, False, 5.5, 7.25),
                index=1,
                kind="matched",
            )
        ],
        params={"use_gpu": False},
        artifacts={"matches_csv": "/work/matches.csv"},
        created_at="2026-06-29T12:00:00+08:00",
    )

    assert payload["schema"] == "autocopy.frame_match.v1"
    assert payload["videos"]["viral"]["fps"] == {"num": 25, "den": 1}
    assert payload["summary"] == {
        "match_count": 1,
        "viral_matched_frames": 10,
        "source_used_frames": 10,
        "viral_total_frames": 100,
        "viral_coverage_ratio": 0.1,
        "unmatched_count": 2,
    }
    assert payload["unmatched"] == [
        {
            "viral": {
                "start_frame": 0,
                "end_frame_exclusive": 10,
                "frame_count": 10,
            },
            "reason": "no_match",
        },
        {
            "viral": {
                "start_frame": 20,
                "end_frame_exclusive": 100,
                "frame_count": 80,
            },
            "reason": "no_match",
        },
    ]
    assert "start_sec" not in str(payload)
    assert "end_sec" not in str(payload)
