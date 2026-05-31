from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..config import settings
from .context import set_current_user_id
from .supervisor import supervisor_node
from .agents.booking_agent import create_booking_agent
from .agents.payment_agent import create_payment_agent
from .agents.customer_service_agent import create_customer_service_agent
from .agents.admin_agent import create_admin_agent


async def _build_user_context(user_id: str, db: AsyncSession) -> str:
    from ..models.user import User
    from ..models.loyalty import LoyaltyAccount
    from ..models.booking import Booking

    context_parts = ["== Current User =="]

    try:
        user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = user_result.scalar_one_or_none()
    except Exception:
        user = None

    if not user:
        context_parts.append("User: Anonymous / Unknown")
        return "\n".join(context_parts)

    context_parts.append(f"User ID: {user_id}")
    context_parts.append(f"Name: {user.name}")
    context_parts.append(f"Email: {user.email}")
    context_parts.append(f"Loyalty Tier: {user.loyalty_tier}")
    context_parts.append(f"Role: {user.role}")

    try:
        loyalty_result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(user_id))
        )
        loyalty = loyalty_result.scalar_one_or_none()
        if loyalty:
            context_parts.append(f"Points Balance: {loyalty.points:,}")
    except Exception:
        pass

    try:
        booking_count_result = await db.execute(
            select(Booking).where(
                Booking.user_id == UUID(user_id),
                Booking.status != "cancelled",
            ).order_by(Booking.created_at.desc()).limit(3)
        )
        recent_bookings = booking_count_result.scalars().all()
        if recent_bookings:
            context_parts.append(f"Recent Bookings: {len(recent_bookings)} (PNRs: {', '.join(b.pnr for b in recent_bookings)})")
        else:
            context_parts.append("Recent Bookings: None (new user)")
    except Exception:
        pass

    context_parts.append("")
    context_parts.append("Adapt behavior by tier:")
    context_parts.append("- Platinum/Gold: Premium service, proactive upgrades, lounge info, priority support")
    context_parts.append("- Silver: Highlight tier progress, suggest earning opportunities")
    context_parts.append("- Bronze/New: Welcome warmly, explain loyalty benefits, guide navigation")
    context_parts.append(f"\nAddress this user as {user.name.split()[0] if user.name else 'there'}. Be personable.")

    return "\n".join(context_parts)


async def _run_sub_agent(agent_name: str, messages: list, user_context: str, user_memories: list[str] | None):
    if agent_name == "booking":
        agent = create_booking_agent(user_context, user_memories)
    elif agent_name == "payment":
        agent = create_payment_agent(user_context, user_memories)
    elif agent_name == "customer_service":
        agent = create_customer_service_agent(user_context, user_memories)
    elif agent_name == "admin":
        agent = create_admin_agent(user_context, user_memories)
    else:
        agent = create_booking_agent(user_context, user_memories)

    result = await agent.ainvoke(
        {"messages": messages},
        config={"recursion_limit": settings.agent_max_iterations},
    )
    return result["messages"]


async def run_agent(
    conversation: list[dict] | str,
    user_id: str,
    session_id: str,
    db: AsyncSession,
    active_agent: str | None = None,
) -> AsyncGenerator[str, None]:
    from ..routers.memory import USER_MEMORIES

    set_current_user_id(user_id)

    user_context = await _build_user_context(user_id, db)

    user_memories = None
    mem_entries = USER_MEMORIES.get(user_id, [])
    if mem_entries:
        user_memories = [m["content"] for m in mem_entries]

    messages = []
    if isinstance(conversation, str):
        messages.append(HumanMessage(content=conversation))
    else:
        for msg in conversation:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant" and msg["content"]:
                messages.append(AIMessage(content=msg["content"]))

    last_user_msg = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user_msg = m.content.lower()
            break

    if active_agent and "end conversation" in last_user_msg:
        content = "Session ended. Feel free to start a new conversation anytime!"
        chunk_size = 500
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
        yield "\n__END_SESSION__"
        return

    state = {
        "messages": messages,
        "active_agent": None,
        "user_context": user_context,
        "user_id": user_id,
        "session_id": session_id,
    }
    result = await supervisor_node(state)
    agent_name = result.get("active_agent")

    if not agent_name:
        end_messages = result.get("messages", [])
        if end_messages:
            content = end_messages[-1].content
        else:
            content = "How can I help you today?"
        chunk_size = 500
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
        yield "\n__END_SESSION__"
        return

    result_messages = await _run_sub_agent(agent_name, messages, user_context, user_memories)

    final_content = ""
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            final_content = msg.content
            break

    if not final_content:
        final_content = "I'm here to help. What would you like to do?"

    chunk_size = 500
    for i in range(0, len(final_content), chunk_size):
        yield final_content[i:i + chunk_size]

    yield f"\n__ACTIVE_AGENT__:{agent_name}"
