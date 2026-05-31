from langgraph.prebuilt import create_react_agent
from datetime import date

from ..llm import get_llm
from ..prompts import PAYMENT_AGENT_PROMPT
from ..tools.payment_tools import get_payment_methods_tool, process_payment_tool, process_refund_tool, get_refund_quote_tool
from ..tools.selfservice_tools import validate_coupon_tool, get_my_loyalty_tool
from ..tools.loyalty_tools import check_loyalty_points_tool

TOOLS = [
    process_payment_tool,
    get_refund_quote_tool,
    process_refund_tool,
    get_payment_methods_tool,
    validate_coupon_tool,
    check_loyalty_points_tool,
    get_my_loyalty_tool,
]


def create_payment_agent(user_context: str, user_memories: list[str] | None = None):
    llm = get_llm(streaming=True)

    prompt = PAYMENT_AGENT_PROMPT.format(
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
