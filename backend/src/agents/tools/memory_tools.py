from langchain_core.tools import tool

_current_user_id: str = "anonymous"


def set_current_user(user_id: str):
    global _current_user_id
    _current_user_id = user_id


@tool
async def save_memory_tool(content: str, category: str = "preference") -> str:
    """Save a piece of information about the user for future conversations. Use this when the user shares preferences, personal details, or asks you to remember something."""
    from ...routers.memory import USER_MEMORIES
    if _current_user_id not in USER_MEMORIES:
        USER_MEMORIES[_current_user_id] = []
    USER_MEMORIES[_current_user_id].append({"content": content, "category": category})
    return f"Memory saved: {content}"


@tool
async def recall_memories_tool() -> str:
    """Recall all stored memories/preferences for the current user."""
    from ...routers.memory import USER_MEMORIES
    memories = USER_MEMORIES.get(_current_user_id, [])
    if not memories:
        return "No stored memories for this user."
    return "\n".join(f"- [{m['category']}] {m['content']}" for m in memories)
