import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..middleware.auth import get_current_user
from ..security.content import sanitize_chat_content

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

CHAT_SESSIONS: dict[str, dict] = {}
TOOL_CALL_LOG: list[dict] = []


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from ..agents.graph import run_agent

    user_id = current_user["sub"] if current_user else "anonymous"
    user_role = current_user.get("role", "user") if current_user else "anonymous"
    user_email = current_user.get("email", "") if current_user else ""
    session_id = body.session_id or str(uuid.uuid4())

    if session_id not in CHAT_SESSIONS:
        CHAT_SESSIONS[session_id] = {
            "user_id": user_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "message_count": 0,
            "status": "active",
            "active_agent": None,
        }

    session = CHAT_SESSIONS[session_id]

    # Reject if an authenticated user tries to resume another user's session.
    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this user")

    session["message_count"] = len(body.messages)

    # Re-validate the cached active_agent against the current user role before
    # trusting it — guards against privilege escalation via stale admin sessions.
    from ..agents.graph import can_route_to_agent
    cached_agent = session.get("active_agent")
    active_agent = cached_agent if (cached_agent is None or can_route_to_agent(cached_agent, user_role)) else None

    try:
        history = [
            {
                "role": message.role,
                "content": sanitize_chat_content(
                    message.content,
                    settings.input_sanitization,
                ),
            }
            for message in body.messages
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def stream():
        nonlocal active_agent
        collected = []
        try:
            async for chunk in run_agent(
                history,
                user_id,
                session_id,
                db,
                active_agent,
                user_role,
                user_email,
            ):
                if chunk.startswith("\n__ACTIVE_AGENT__:"):
                    agent_name = chunk.split(":", 1)[1]
                    session["active_agent"] = agent_name
                    data = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now(timezone.utc).timestamp()),
                        "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": None}],
                        "session_id": session_id,
                        "active_agent": agent_name,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    continue
                if chunk.strip() == "__END_SESSION__" or chunk.strip() == "\n__END_SESSION__":
                    session["active_agent"] = None
                    data = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now(timezone.utc).timestamp()),
                        "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": None}],
                        "session_id": session_id,
                        "active_agent": None,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    continue

                collected.append(chunk)
                data = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    "object": "chat.completion.chunk",
                    "created": int(datetime.now(timezone.utc).timestamp()),
                    "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    "session_id": session_id,
                    "active_agent": session.get("active_agent"),
                }
                yield f"data: {json.dumps(data)}\n\n"
        except Exception as e:
            error_data = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion.chunk",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "error"}],
                "error": str(e),
                "session_id": session_id,
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        session["status"] = "completed"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/sessions")
async def list_sessions():
    return {"sessions": list(CHAT_SESSIONS.values())[-50:], "total": len(CHAT_SESSIONS)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = CHAT_SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}
    return session


@router.get("/tool-calls")
async def list_tool_calls():
    return {"tool_calls": TOOL_CALL_LOG[-100:], "total": len(TOOL_CALL_LOG)}
