from langgraph.prebuilt import create_react_agent
from datetime import date

from ..llm import get_llm
from ..prompts import CUSTOMER_SERVICE_PROMPT
from ..tools.user_tools import get_user_profile_tool, lookup_user_tool
from ..tools.email_tools import send_email_tool, get_sent_emails_tool
from ..tools.loyalty_tools import check_loyalty_points_tool, modify_loyalty_points_tool
from ..tools.memory_tools import save_memory_tool, recall_memories_tool
from ..tools.selfservice_tools import lookup_policy_tool, get_my_loyalty_tool
from ..tools.booking_tools import cancel_booking_tool, get_cancellation_quote_tool

TOOLS = [
    get_user_profile_tool,
    lookup_user_tool,
    send_email_tool,
    get_sent_emails_tool,
    check_loyalty_points_tool,
    modify_loyalty_points_tool,
    save_memory_tool,
    recall_memories_tool,
    lookup_policy_tool,
    get_my_loyalty_tool,
    get_cancellation_quote_tool,
    cancel_booking_tool,
]


def create_customer_service_agent(user_context: str, user_memories: list[str] | None = None):
    llm = get_llm(streaming=True)

    prompt = CUSTOMER_SERVICE_PROMPT.format(
        today=date.today().isoformat(),
        user_context=user_context,
    )
    if user_memories:
        prompt += "\n\nUser preferences (always follow these):\n" + "\n".join(f"- {m}" for m in user_memories)

    return create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=prompt,
    )
