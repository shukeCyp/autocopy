import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path(".data/settings.json")

DEFAULT_SETTINGS: dict[str, Any] = {
    "paths": {
        "rewrite_dir": "/Users/chaiyapeng/Downloads/爆款文案洗稿",
        "video_match_dir": "/Users/chaiyapeng/Downloads/video",
        "output_dir": str(Path.cwd() / "output"),
        "whisper_model": "ggml-large-v3-turbo.bin",
        "vad_model": "ggml-silero-v6.2.0.bin",
    },
    "llm": {
        "provider": "Gemini网关",
        "model": "gemini-3.5-flash",
        "base_url": "https://yunwu.ai",
        "api_key": "",
    },
    "tts_extract": {
        "refresh_gemini": False,
        "min_word_overlap": 0.85,
    },
    "rewrite": {
        "target_language": "Chinese",
        "style": "localized short-video crime recap",
        "max_segment_seconds": 30,
        "max_gap_ms": 700,
    },
    "vad": {
        "threshold": 0.25,
        "min_speech_ms": 10,
        "min_silence_ms": 50,
    },
    "video_match": {
        "gpu_enabled": False,
    },
    "minimax": {
        "base_url": "https://api.minimax.chat",
        "group_id": "",
        "api_key": "",
        "model": "speech-02-hd",
        "voice_id": "",
        "speed": 1.0,
        "volume": 1.0,
        "pitch": 0,
        "audio_format": "mp3",
    },
    "compose": {
        "keep_temp": True,
        "video_codec": "libx264",
        "audio_codec": "aac",
    },
}


def merge_defaults(value: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(default)
    for key, item in value.items():
        if isinstance(item, dict) and isinstance(result.get(key), dict):
            result[key] = merge_defaults(item, result[key])
        else:
            result[key] = item
    return result


def load_settings() -> dict[str, Any]:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        settings = merge_defaults(json.loads(SETTINGS_PATH.read_text("utf-8")), DEFAULT_SETTINGS)
    else:
        settings = deepcopy(DEFAULT_SETTINGS)
    settings["video_match"] = {
        "gpu_enabled": bool(settings.get("video_match", {}).get("gpu_enabled", DEFAULT_SETTINGS["video_match"]["gpu_enabled"]))
    }
    save_settings(settings)
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", "utf-8")
