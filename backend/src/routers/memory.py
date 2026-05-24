from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])

USER_MEMORIES: dict[str, list[dict]] = {}


class MemoryEntry(BaseModel):
    content: str
    category: str = "preference"


@router.post("/store")
async def store_memory(
    body: MemoryEntry,
    current_user: dict | None = Depends(get_current_user),
):
    user_id = current_user["sub"] if current_user else "anonymous"
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    USER_MEMORIES[user_id].append({"content": body.content, "category": body.category})
    return {"status": "stored", "total_memories": len(USER_MEMORIES[user_id])}


@router.get("/recall")
async def recall_memories(
    current_user: dict | None = Depends(get_current_user),
):
    user_id = current_user["sub"] if current_user else "anonymous"
    return {"memories": USER_MEMORIES.get(user_id, [])}


@router.delete("/clear")
async def clear_memories(
    current_user: dict | None = Depends(get_current_user),
):
    user_id = current_user["sub"] if current_user else "anonymous"
    USER_MEMORIES.pop(user_id, None)
    return {"status": "cleared"}
