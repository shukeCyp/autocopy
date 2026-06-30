from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.vmf_match import run_vmf_match


def test_run_vmf_match_converts_vmf_results_to_frame_match_json(tmp_path):
    viral = tmp_path / "viral.mp4"
    source = tmp_path / "source.mp4"
    viral.write_bytes(b"viral")
    source.write_bytes(b"source")

    def fake_run(cmd, check, stdout=None, stderr=None, env=None):
        if Path(cmd[0]).name == "vmf":
            json_path = Path(cmd[cmd.index("--json") + 1])
            json_path.write_text(json.dumps([
                {
                    "a": {"id": 1, "path": str(viral.resolve())},
                    "b": {"id": 2, "path": str(source.resolve())},
                    "segments": [
                        {
                            "a_range": [1.0, 4.0],
                            "b_range": [10.0, 16.0],
                            "speed_ratio": 2.0,
                            "mirrored": True,
                            "score": 0.91,
                            "inliers": 12,
                            "pvalue": 0.01,
                            "z_score": 7.5,
                            "weighted_support": 42.0,
                        }
                    ],
                }
            ]), encoding="utf-8")

    with patch("app.vmf_match.shutil.which", return_value="/usr/bin/vmf"), \
            patch("app.vmf_match.subprocess.run", side_effect=fake_run) as mock_run:
        result = run_vmf_match(
            viral,
            source,
            tmp_path / "out",
            viral_video_info={"fps": 30.0, "frame_count": 300, "width": 1080, "height": 1920},
            source_video_info={"fps": 24.0, "frame_count": 2400, "width": 1920, "height": 1080},
            vmf_bin="vmf",
            fps=2.5,
            model="dinov2_vits14",
            device="cpu",
            no_mirror=False,
            keyframes_only=True,
            no_cropdetect=True,
            legacy_ransac=True,
        )

    assert set(result) == {"segments_json", "vmf_results_json"}
    assert Path(result["vmf_results_json"]).exists()
    payload = json.loads(Path(result["segments_json"]).read_text(encoding="utf-8"))
    assert payload["schema"] == "autocopy.frame_match.v1"
    assert payload["producer"]["engine"] == "vmf"
    assert payload["videos"]["viral"]["fps"] == {"num": 30, "den": 1}
    assert payload["videos"]["source"]["fps"] == {"num": 24, "den": 1}
    assert payload["matches"] == [
        {
            "id": "match_0001",
            "index": 1,
            "kind": "matched",
            "viral": {
                "start_frame": 30,
                "end_frame_exclusive": 120,
                "frame_count": 90,
            },
            "source": {
                "start_frame": 240,
                "end_frame_exclusive": 384,
                "frame_count": 144,
            },
            "mapping": {
                "type": "linear",
                "source_per_viral": {"num": 144, "den": 90},
                "rounding": "nearest",
            },
            "transform": {
                "mirrored": True,
                "crop": {
                    "x": None,
                    "y": None,
                    "width": None,
                    "height": None,
                    "unit": "px",
                },
            },
            "quality": {
                "primary": {
                    "name": "vmf_score",
                    "value": 0.91,
                    "higher_is_better": True,
                },
                "metrics": {
                    "inliers": 12,
                    "pvalue": 0.01,
                    "z_score": 7.5,
                    "weighted_support": 42.0,
                    "speed_ratio": 2.0,
                },
            },
            "engine": {"name": "vmf"},
        }
    ]
    assert "start_sec" not in str(payload)
    assert "end_sec" not in str(payload)

    vmf_cmd = mock_run.call_args_list[0].args[0]
    assert Path(vmf_cmd[0]).name == "vmf"
    assert vmf_cmd[1] == "scan"
    assert "--json" in vmf_cmd
    assert "--keyframes-only" in vmf_cmd
    assert "--no-cropdetect" in vmf_cmd
    assert "--legacy-ransac" in vmf_cmd
    assert len(mock_run.call_args_list) == 1
    vmf_env = mock_run.call_args_list[0].kwargs["env"]
    assert vmf_env["KMP_DUPLICATE_LIB_OK"] == "TRUE"
    assert vmf_env["OMP_NUM_THREADS"] == "1"
    assert vmf_env["MKL_NUM_THREADS"] == "1"
    assert vmf_env["VECLIB_MAXIMUM_THREADS"] == "1"
    assert vmf_env["OPENBLAS_NUM_THREADS"] == "1"
    assert vmf_env["NUMEXPR_NUM_THREADS"] == "1"
    assert vmf_env["TORCH_HOME"] == str((Path("model") / "torch").resolve())
    assert vmf_env["HF_HOME"] == str((Path("model") / "huggingface").resolve())
    assert vmf_env["HUGGINGFACE_HUB_CACHE"] == str((Path("model") / "huggingface" / "hub").resolve())


def test_run_vmf_match_finds_vmf_next_to_current_python_when_not_on_path(tmp_path):
    viral = tmp_path / "viral.mp4"
    source = tmp_path / "source.mp4"
    python_bin = tmp_path / "venv" / "bin" / "python"
    vmf_bin = python_bin.parent / "vmf"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("")
    vmf_bin.write_text("")
    vmf_bin.chmod(0o755)
    viral.write_bytes(b"viral")
    source.write_bytes(b"source")

    def fake_run(cmd, check, stdout=None, stderr=None, env=None):
        assert cmd[0] == str(vmf_bin)
        json_path = Path(cmd[cmd.index("--json") + 1])
        json_path.write_text(json.dumps([
            {
                "a": {"id": 1, "path": str(viral.resolve())},
                "b": {"id": 2, "path": str(source.resolve())},
                "segments": [
                    {
                        "a_range": [0.0, 1.0],
                        "b_range": [2.0, 3.0],
                        "score": 0.8,
                    }
                ],
            }
        ]), encoding="utf-8")

    with patch("app.vmf_match.shutil.which", return_value=None), \
            patch("app.vmf_match.sys.executable", str(python_bin)), \
            patch("app.vmf_match.subprocess.run", side_effect=fake_run) as mock_run:
        result = run_vmf_match(
            viral,
            source,
            tmp_path / "out",
            viral_video_info={"fps": 30.0, "frame_count": 30, "width": 1080, "height": 1920},
            source_video_info={"fps": 24.0, "frame_count": 240, "width": 1920, "height": 1080},
        )

    assert Path(result["segments_json"]).exists()
    vmf_cmd = mock_run.call_args_list[0].args[0]
    assert vmf_cmd[vmf_cmd.index("--model") + 1] == "dinov2_vits14"


def test_run_vmf_match_finds_vmf_next_to_python_symlink_when_not_on_path(tmp_path):
    viral = tmp_path / "viral.mp4"
    source = tmp_path / "source.mp4"
    real_python = tmp_path / "python-install" / "bin" / "python3"
    python_bin = tmp_path / "venv" / "bin" / "python"
    vmf_bin = python_bin.parent / "vmf"
    real_python.parent.mkdir(parents=True)
    python_bin.parent.mkdir(parents=True)
    real_python.write_text("")
    python_bin.symlink_to(real_python)
    vmf_bin.write_text("")
    vmf_bin.chmod(0o755)
    viral.write_bytes(b"viral")
    source.write_bytes(b"source")

    def fake_run(cmd, check, stdout=None, stderr=None, env=None):
        assert cmd[0] == str(vmf_bin)
        json_path = Path(cmd[cmd.index("--json") + 1])
        json_path.write_text(json.dumps([
            {
                "a": {"id": 1, "path": str(viral.resolve())},
                "b": {"id": 2, "path": str(source.resolve())},
                "segments": [
                    {
                        "a_range": [0.0, 1.0],
                        "b_range": [2.0, 3.0],
                        "score": 0.8,
                    }
                ],
            }
        ]), encoding="utf-8")

    with patch("app.vmf_match.shutil.which", return_value=None), \
            patch("app.vmf_match.sys.executable", str(python_bin)), \
            patch("app.vmf_match.subprocess.run", side_effect=fake_run):
        result = run_vmf_match(
            viral,
            source,
            tmp_path / "out",
            viral_video_info={"fps": 30.0, "frame_count": 30, "width": 1080, "height": 1920},
            source_video_info={"fps": 24.0, "frame_count": 240, "width": 1920, "height": 1080},
        )

    assert Path(result["segments_json"]).exists()


def test_run_vmf_match_reports_missing_cli(tmp_path):
    python_bin = tmp_path / "venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("")

    with patch("app.vmf_match.shutil.which", return_value=None), \
            patch("app.vmf_match.sys.executable", str(python_bin)):
        try:
            run_vmf_match("viral.mp4", "source.mp4", tmp_path)
        except RuntimeError as exc:
            assert "VMF command not found" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_run_vmf_match_writes_empty_result_when_vmf_finds_no_segments(tmp_path):
    viral = tmp_path / "viral.mp4"
    source = tmp_path / "source.mp4"
    viral.write_bytes(b"viral")
    source.write_bytes(b"source")

    def fake_run(cmd, check, stdout=None, stderr=None, env=None):
        json_path = Path(cmd[cmd.index("--json") + 1])
        json_path.write_text("[]", encoding="utf-8")

    with patch("app.vmf_match.shutil.which", return_value="/usr/bin/vmf"), \
            patch("app.vmf_match.subprocess.run", side_effect=fake_run):
        result = run_vmf_match(
            viral,
            source,
            tmp_path / "out",
            viral_video_info={"fps": 30.0, "frame_count": 90, "width": 1080, "height": 1920},
            source_video_info={"fps": 24.0, "frame_count": 240, "width": 1920, "height": 1080},
        )

    payload = json.loads(Path(result["segments_json"]).read_text(encoding="utf-8"))
    assert payload["matches"] == []
    assert payload["summary"]["match_count"] == 0
    assert payload["summary"]["viral_coverage_ratio"] == 0.0
    assert payload["unmatched"] == [
        {
            "viral": {
                "start_frame": 0,
                "end_frame_exclusive": 90,
                "frame_count": 90,
            },
            "reason": "no_match",
        }
    ]
    assert payload["warnings"] == ["VMF did not find matching segments for the selected video pair"]
    assert json.loads(Path(result["vmf_results_json"]).read_text(encoding="utf-8")) == []


def test_run_vmf_match_reports_vmf_stdout_and_stderr(tmp_path):
    viral = tmp_path / "viral.mp4"
    source = tmp_path / "source.mp4"
    viral.write_bytes(b"viral")
    source.write_bytes(b"source")

    def fake_run(cmd, check, stdout=None, stderr=None, env=None):
        raise subprocess.CalledProcessError(
            returncode=-11,
            cmd=cmd,
            output=b"Found 2 video(s).\n",
            stderr=b"Loading dinov2_vits14 on cpu\n",
        )

    import subprocess

    with patch("app.vmf_match.shutil.which", return_value="/usr/bin/vmf"), \
            patch("app.vmf_match.subprocess.run", side_effect=fake_run):
        try:
            run_vmf_match(
                viral,
                source,
                tmp_path / "out",
                viral_video_info={"fps": 30.0, "frame_count": 30, "width": 1080, "height": 1920},
                source_video_info={"fps": 24.0, "frame_count": 240, "width": 1920, "height": 1080},
            )
        except RuntimeError as exc:
            message = str(exc)
            assert "VMF command failed" in message
            assert "Found 2 video(s)." in message
            assert "Loading dinov2_vits14 on cpu" in message
        else:
            raise AssertionError("expected RuntimeError")
