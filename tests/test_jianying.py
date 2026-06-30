import json
import sys
from types import SimpleNamespace

import pytest

from app.jianying import create_jianying_merge_draft, safe_draft_name


def test_safe_draft_name_uses_viral_video_stem():
    assert safe_draft_name("/tmp/对标爆款:测试?.mp4") == "对标爆款_测试_"


def test_create_jianying_merge_draft_places_matched_video_and_srt(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    segments_json = tmp_path / "segments.json"
    srt_path = tmp_path / "rewritten.srt"
    segments_json.write_text(json.dumps({
        "schema": "autocopy.frame_match.v1",
        "videos": {
            "viral": {
                "path": str(tmp_path / "viral.mp4"),
                "fps": {"num": 30, "den": 1},
                "width": 1080,
                "height": 1920,
            },
            "source": {
                "path": str(source),
                "fps": {"num": 24, "den": 1},
                "width": 1920,
                "height": 1080,
            },
        },
        "matches": [
            {
                "viral": {
                    "start_frame": 0,
                    "end_frame_exclusive": 30,
                    "frame_count": 30,
                },
                "source": {
                    "start_frame": 240,
                    "end_frame_exclusive": 288,
                    "frame_count": 48,
                },
                "transform": {"mirrored": False},
            }
        ],
    }), encoding="utf-8")
    srt_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n字幕一\n\n"
        "2\n00:00:01,200 --> 00:00:02,000\n字幕二\n",
        encoding="utf-8",
    )
    fake = _install_fake_pycapcut(monkeypatch)

    draft_path = create_jianying_merge_draft(
        segments_json,
        srt_path,
        draft_folder=tmp_path / "drafts",
        draft_name="合并:草稿?",
    )

    assert draft_path == tmp_path / "drafts" / "合并_草稿_"
    assert fake.script.created == ("合并_草稿_", 1080, 1920, 30, True)
    assert fake.script.tracks == [("video", "matched_video"), ("text", "srt_subtitles")]
    video_segment = fake.script.segments[0][0]
    assert video_segment.material == str(source)
    assert video_segment.target_timerange == {"start": 0.0, "duration": 1.0}
    assert video_segment.source_timerange == {"start": 10.0, "duration": 2.0}
    assert video_segment.speed == 2.0
    assert [(segment.text, segment.timerange) for segment, track in fake.script.segments[1:]] == [
        ("字幕一", {"start": 0.0, "duration": 1.0}),
        ("字幕二", {"start": 1.2, "duration": 0.8}),
    ]
    assert [track for segment, track in fake.script.segments] == [
        "matched_video",
        "srt_subtitles",
        "srt_subtitles",
    ]
    assert fake.script.saved is True


def test_create_jianying_merge_draft_requires_frame_match_json(tmp_path):
    segments_json = tmp_path / "segments.json"
    srt_path = tmp_path / "rewritten.srt"
    segments_json.write_text("[]", encoding="utf-8")
    srt_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="frame match"):
        create_jianying_merge_draft(segments_json, srt_path, draft_folder=tmp_path)


def test_create_jianying_merge_draft_allows_empty_matches(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    segments_json = tmp_path / "segments.json"
    srt_path = tmp_path / "rewritten.srt"
    segments_json.write_text(json.dumps({
        "schema": "autocopy.frame_match.v1",
        "videos": {
            "viral": {
                "path": str(tmp_path / "viral.mp4"),
                "fps": {"num": 25, "den": 1},
                "width": 1080,
                "height": 1440,
            },
            "source": {
                "path": str(source),
                "fps": {"num": 24000, "den": 1001},
                "width": 1920,
                "height": 1080,
            },
        },
        "summary": {"match_count": 0},
        "matches": [],
        "warnings": ["VMF did not find matching segments for the selected video pair"],
    }), encoding="utf-8")
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n字幕一\n", encoding="utf-8")
    fake = _install_fake_pycapcut(monkeypatch)

    draft_path = create_jianying_merge_draft(
        segments_json,
        srt_path,
        draft_folder=tmp_path / "drafts",
    )

    assert draft_path == tmp_path / "drafts" / "viral"
    assert fake.script.created == ("viral", 1080, 1440, 25, True)
    assert fake.script.tracks == [("video", "matched_video"), ("text", "srt_subtitles")]
    assert [(segment.text, track) for segment, track in fake.script.segments] == [("字幕一", "srt_subtitles")]
    assert fake.script.saved is True


def _install_fake_pycapcut(monkeypatch):
    state = SimpleNamespace(script=None)

    class TrackType:
        video = "video"
        text = "text"

    class VideoSegment:
        def __init__(self, material, target_timerange, *, source_timerange=None, speed=None, volume=1.0, clip_settings=None):
            self.material = material
            self.target_timerange = target_timerange
            self.source_timerange = source_timerange
            self.speed = speed
            self.volume = volume
            self.clip_settings = clip_settings

    class TextStyle:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class TextBorder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class TextSegment:
        def __init__(self, text, timerange, *, font=None, style=None, clip_settings=None, border=None, background=None):
            self.text = text
            self.timerange = timerange
            self.font = font
            self.style = style
            self.clip_settings = clip_settings
            self.border = border
            self.background = background

    class Script:
        def __init__(self, created):
            self.created = created
            self.tracks = []
            self.segments = []
            self.saved = False

        def add_track(self, track_type, track_name=None, **kwargs):
            self.tracks.append((track_type, track_name))
            return self

        def add_segment(self, segment, track_name=None):
            self.segments.append((segment, track_name))
            return self

        def save(self):
            self.saved = True

    class DraftFolder:
        def __init__(self, folder_path):
            self.folder_path = folder_path

        def create_draft(self, draft_name, width, height, fps=30, *, allow_replace=False):
            state.script = Script((draft_name, width, height, fps, allow_replace))
            return state.script

    def trange(start, duration):
        return {"start": float(start), "duration": float(duration)}

    monkeypatch.setitem(sys.modules, "pycapcut", SimpleNamespace(
        DraftFolder=DraftFolder,
        TrackType=TrackType,
        VideoSegment=VideoSegment,
        TextSegment=TextSegment,
        TextStyle=TextStyle,
        TextBorder=TextBorder,
        trange=trange,
    ))
    return state
