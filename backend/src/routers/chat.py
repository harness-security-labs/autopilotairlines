import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

CHAT_SESSIONS: dict[str, dict] = {}
TOOL_CALL_LOG: list[dict] = []


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from ..agents.graph import run_agent

    user_id = current_user["sub"] if current_user else "anonymous"
    session_id = str(uuid.uuid4())

    history = [{"role": m.role, "content": m.content} for m in body.messages]

    CHAT_SESSIONS[session_id] = {
        "user_id": user_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(body.messages),
        "status": "active",
    }

    async def stream():
        async for chunk in run_agent(history, user_id, session_id, db):
            data = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion.chunk",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(data)}\n\n"
        CHAT_SESSIONS[session_id]["status"] = "completed"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/sessions")
async def list_sessions():
    return {"sessions": list(CHAT_SESSIONS.values())[-50:], "total": len(CHAT_SESSIONS)}


@router.get("/tool-calls")
async def list_tool_calls():
    return {"tool_calls": TOOL_CALL_LOG[-100:], "total": len(TOOL_CALL_LOG)}
