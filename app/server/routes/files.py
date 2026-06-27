from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = Path(".data/uploads")


def _safe_name(filename: str) -> str:
    name = Path(filename or "upload.bin").name
    return name.replace("/", "_").replace("\\", "_")


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

