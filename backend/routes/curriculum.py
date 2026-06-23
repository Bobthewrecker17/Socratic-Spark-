import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.rag import ingest_curriculum
from services.url_fetcher import fetch_url_as_text
from db.session_store import create_session, get_default_mode

router = APIRouter()

VALID_MODES = ("strict", "discovery")


class UploadResponse(BaseModel):
    session_id: str
    chunks_stored: int
    mode: str = "discovery"


class UrlUploadRequest(BaseModel):
    subject: str
    url: str
    mode: Optional[str] = None  # student choice; falls back to teacher default


class UrlUploadResponse(BaseModel):
    session_id: str
    chunks_stored: int
    error: str = ""
    mode: str = "discovery"


@router.post("/upload", response_model=UploadResponse)
async def upload_curriculum(
    subject: str = Form(...),
    file: UploadFile = File(...),
    mode: Optional[str] = Form(default=None),
):
    if not subject.strip():
        raise HTTPException(status_code=422, detail="Subject cannot be empty.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    # Student choice overrides teacher default; fall back to teacher default
    resolved_mode = mode if mode in VALID_MODES else await get_default_mode()

    session_id = str(uuid.uuid4())
    await create_session(session_id, subject.strip(), mode=resolved_mode)

    chunks_stored = await ingest_curriculum(
        content=content,
        filename=file.filename or "upload.txt",
        subject=subject.strip(),
        session_id=session_id,
    )

    return UploadResponse(session_id=session_id, chunks_stored=chunks_stored, mode=resolved_mode)


@router.post("/upload-url", response_model=UrlUploadResponse)
async def upload_curriculum_url(req: UrlUploadRequest):
    if not req.subject.strip():
        raise HTTPException(status_code=422, detail="Subject cannot be empty.")
    if not req.url.strip():
        raise HTTPException(status_code=422, detail="URL cannot be empty.")

    text, error = await fetch_url_as_text(req.url.strip())
    if error:
        return UrlUploadResponse(session_id="", chunks_stored=0, error=error)

    resolved_mode = req.mode if req.mode in VALID_MODES else await get_default_mode()

    session_id = str(uuid.uuid4())
    await create_session(session_id, req.subject.strip(), mode=resolved_mode)

    chunks_stored = await ingest_curriculum(
        content=text.encode("utf-8"),
        filename="webpage.txt",
        subject=req.subject.strip(),
        session_id=session_id,
    )

    return UrlUploadResponse(session_id=session_id, chunks_stored=chunks_stored, mode=resolved_mode)
