from langgraph.prebuilt import create_react_agent
from datetime import date

from ...config import settings
from ..llm import get_llm
from ..prompts import ADMIN_AGENT_PROMPT
from ..prompt_utils import append_untrusted_user_memories
from ..tools.user_tools import list_users_tool, get_user_profile_tool, lookup_user_tool
from ..tools.loyalty_tools import modify_loyalty_points_tool
from ..tools.email_tools import send_email_tool, get_sent_emails_tool
from ..tools.debug_tools import generate_flight_report_tool

TOOLS = [
    list_users_tool,
    get_user_profile_tool,
    lookup_user_tool,
    modify_loyalty_points_tool,
    send_email_tool,
    get_sent_emails_tool,
    generate_flight_report_tool,
]


def create_admin_agent(user_context: str, user_memories: list[str] | None = None):
    llm = get_llm(streaming=True)

    tools = list(TOOLS)

    if settings.debug_tools_enabled:
        from ..tools.debug_tools import debug_query_tool
        tools.append(debug_query_tool)

    prompt = ADMIN_AGENT_PROMPT.format(
        today=date.today().isoformat(),
        user_context=user_context,
    )
    prompt = append_untrusted_user_memories(prompt, user_memories)

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
    )
