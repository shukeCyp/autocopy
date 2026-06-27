import json

from app.settings import DEFAULT_SETTINGS, SETTINGS_PATH, load_settings, save_settings


def test_load_settings_creates_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    settings = load_settings()

    assert settings == DEFAULT_SETTINGS
    assert SETTINGS_PATH.exists()
    assert json.loads(SETTINGS_PATH.read_text("utf-8")) == DEFAULT_SETTINGS


def test_load_settings_merges_existing_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    SETTINGS_PATH.parent.mkdir(parents=True)
    SETTINGS_PATH.write_text(
        json.dumps({"llm": {"model": "custom-model"}, "vad": {"threshold": 0.33}}),
        "utf-8",
    )

    settings = load_settings()

    assert settings["llm"]["model"] == "custom-model"
    assert settings["llm"]["base_url"] == DEFAULT_SETTINGS["llm"]["base_url"]
    assert settings["vad"]["threshold"] == 0.33


def test_load_settings_prunes_video_match_tuning_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    SETTINGS_PATH.parent.mkdir(parents=True)
    SETTINGS_PATH.write_text(
        json.dumps({"video_match": {"gpu_enabled": True, "score_percentile": 90}}),
        "utf-8",
    )

    settings = load_settings()

    assert settings["video_match"] == {"gpu_enabled": True}
    assert json.loads(SETTINGS_PATH.read_text("utf-8"))["video_match"] == {"gpu_enabled": True}


def test_save_settings_writes_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    settings["minimax"]["voice_id"] = "voice-1"

    save_settings(settings)

    assert json.loads(SETTINGS_PATH.read_text("utf-8"))["minimax"]["voice_id"] == "voice-1"
