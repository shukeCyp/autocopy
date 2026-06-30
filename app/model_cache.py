from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


MODEL_DIR_ENV = "AUTOCOPY_MODEL_DIR"
DEFAULT_MODEL_DIR = "model"


def model_dir() -> Path:
    return Path(os.environ.get(MODEL_DIR_ENV, DEFAULT_MODEL_DIR)).expanduser().resolve()


def model_cache_path(*parts: str) -> Path:
    return model_dir().joinpath(*parts)


def model_cache_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    root = model_dir()
    root.mkdir(parents=True, exist_ok=True)

    env["TORCH_HOME"] = str(root / "torch")
    env["HF_HOME"] = str(root / "huggingface")
    env["HUGGINGFACE_HUB_CACHE"] = str(root / "huggingface" / "hub")
    env["TRANSFORMERS_CACHE"] = str(root / "huggingface" / "transformers")
    return env
