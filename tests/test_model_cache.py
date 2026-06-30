from pathlib import Path

from app.model_cache import model_cache_env, model_cache_path


def test_model_cache_path_defaults_to_project_model_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert model_cache_path("torch") == (tmp_path / "model" / "torch").resolve()


def test_model_cache_env_routes_model_downloads_to_model_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    env = model_cache_env({"EXISTING": "1", "TORCH_HOME": "/old/cache"})

    model_dir = (tmp_path / "model").resolve()
    assert env["EXISTING"] == "1"
    assert env["TORCH_HOME"] == str(model_dir / "torch")
    assert env["HF_HOME"] == str(model_dir / "huggingface")
    assert env["HUGGINGFACE_HUB_CACHE"] == str(model_dir / "huggingface" / "hub")
    assert env["TRANSFORMERS_CACHE"] == str(model_dir / "huggingface" / "transformers")
    assert model_dir.is_dir()
