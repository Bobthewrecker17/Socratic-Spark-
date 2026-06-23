from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.input_filter import filter_input
from services.rag import retrieve_context
from services.tutor import build_system_prompt, call_claude
from services.output_validator import validated_completion
from db.session_store import (
    get_session_history,
    log_message,
    log_blocked_attempt,
    check_rate_limit,
    get_session_messages_public,
    get_session_mode,
    update_session_mode,
)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    blocked: bool
    reason: str = ""
    reply: str = ""
    validator_retries: int = 0
    mode: str = "discovery"


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id
    user_message = req.message.strip()

    if not user_message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    # Rate limit check
    within_limit = await check_rate_limit(session_id)
    if not within_limit:
        return ChatResponse(
            blocked=True,
            reason="Rate limit exceeded.",
            reply="",
        )

    # Layer 1: Input filter
    filter_result = await filter_input(user_message)
    if filter_result["blocked"]:
        await log_blocked_attempt(session_id, user_message, filter_result["reason"])
        await log_message(session_id, "user", user_message, was_blocked=True)
        return ChatResponse(blocked=True, reason=filter_result["reason"])

    # Layer 2: RAG — retrieve relevant chunks
    chunks = await retrieve_context(user_message, session_id)

    # Layer 3: Build hardened system prompt (mode-aware)
    mode = await get_session_mode(session_id)
    system_prompt = build_system_prompt(chunks, mode=mode)

    # Fetch conversation history and append current message
    history = await get_session_history(session_id)
    history.append({"role": "user", "content": user_message})

    # Layer 4: Output validation with retries
    reply, retries = await validated_completion(
        make_completion=call_claude,
        system_prompt=system_prompt,
        messages=history,
    )

    # Layer 5: Persist to audit log
    await log_message(session_id, "user", user_message, was_blocked=False, validator_retries=0)
    await log_message(session_id, "assistant", reply, was_blocked=False, validator_retries=retries)

    return ChatResponse(blocked=False, reply=reply, validator_retries=retries, mode=mode)


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    messages = await get_session_messages_public(session_id)
    mode = await get_session_mode(session_id)
    return {"session_id": session_id, "messages": messages, "mode": mode}


class ModeUpdate(BaseModel):
    mode: str


@router.patch("/{session_id}/mode")
async def set_session_mode(session_id: str, body: ModeUpdate):
    if body.mode not in ("strict", "discovery"):
        raise HTTPException(status_code=422, detail="mode must be 'strict' or 'discovery'.")
    await update_session_mode(session_id, body.mode)
    return {"session_id": session_id, "mode": body.mode}
