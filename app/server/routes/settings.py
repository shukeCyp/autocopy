from __future__ import annotations

from fastapi import APIRouter

from app.server.database import get_settings, save_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def api_get_settings():
    return await get_settings()


@router.put("")
async def api_save_settings(body: dict):
    return await save_settings(body)
