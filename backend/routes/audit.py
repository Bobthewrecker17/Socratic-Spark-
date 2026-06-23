import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from db.session_store import (
    get_audit_log,
    get_all_sessions,
    get_default_mode,
    set_default_mode,
    update_session_mode,
)

router = APIRouter()

TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "changeme")


def _check_auth(authorization: str | None):
    if authorization != f"Bearer {TEACHER_PASSWORD}":
        raise HTTPException(status_code=401, detail="Unauthorized.")


@router.get("/settings")
async def get_settings(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    mode = await get_default_mode()
    return {"default_mode": mode}


class SettingsUpdate(BaseModel):
    default_mode: str


@router.post("/settings")
async def update_settings(
    body: SettingsUpdate,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)
    if body.default_mode not in ("strict", "discovery"):
        raise HTTPException(status_code=422, detail="mode must be 'strict' or 'discovery'.")
    await set_default_mode(body.default_mode)
    return {"default_mode": body.default_mode}


class SessionModeUpdate(BaseModel):
    mode: str


@router.patch("/{session_id}/mode")
async def patch_session_mode(
    session_id: str,
    body: SessionModeUpdate,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)
    if body.mode not in ("strict", "discovery"):
        raise HTTPException(status_code=422, detail="mode must be 'strict' or 'discovery'.")
    await update_session_mode(session_id, body.mode)
    return {"session_id": session_id, "mode": body.mode}


@router.get("/sessions")
async def list_sessions(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    sessions = await get_all_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session_audit(
    session_id: str,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)
    log = await get_audit_log(session_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return log
