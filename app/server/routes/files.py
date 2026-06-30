from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = Path(".data/uploads")
MODEL_DIR = Path("model")


def _safe_name(filename: str) -> str:
    name = Path(filename or "upload.bin").name
    return name.replace("/", "_").replace("\\", "_")


def select_directory() -> Path | None:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'POSIX path of (choose folder with prompt "选择剪映草稿目录")',
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError:
            return None
        selected = result.stdout.strip()
        return Path(selected) if selected else None

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="选择剪映草稿目录")
        root.destroy()
    except Exception as exc:
        raise RuntimeError(f"directory picker unavailable: {exc}") from exc
    return Path(selected) if selected else None


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}-{_safe_name(file.filename)}"

    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    path = str(target.resolve())
    return {
        "path": path,
        "name": file.filename,
        "size": target.stat().st_size,
    }


@router.post("/select-directory")
async def select_directory_endpoint():
    try:
        selected = select_directory()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": str(selected.expanduser().resolve()) if selected else ""}


@router.get("/models")
async def list_models():
    if not MODEL_DIR.exists():
        return []

    files = []
    for path in sorted(MODEL_DIR.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            files.append(str(path.relative_to(MODEL_DIR)))
    return files
