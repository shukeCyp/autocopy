from app.jianying import safe_draft_name


def test_safe_draft_name_uses_viral_video_stem():
    assert safe_draft_name("/tmp/对标爆款:测试?.mp4") == "对标爆款_测试_"
