from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from datetime import date

from ..llm import get_llm
from ..prompts import BOOKING_AGENT_PROMPT
from ..tools.flight_tools import search_flights_tool, get_flight_tool
from ..tools.booking_tools import create_booking_tool, cancel_booking_tool, book_connecting_flight_tool, reschedule_booking_tool, get_reschedule_quote_tool, get_booking_quote_tool, get_cancellation_quote_tool, get_connecting_flight_quote_tool
from ..tools.selfservice_tools import (
    get_my_bookings_tool,
    get_booking_details_tool,
    validate_coupon_tool,
    check_flight_status_tool,
    get_my_loyalty_tool,
    get_refund_history_tool,
)
from ..tools.payment_tools import get_payment_methods_tool, process_payment_tool

TOOLS = [
    search_flights_tool,
    get_flight_tool,
    get_booking_quote_tool,
    create_booking_tool,
    get_cancellation_quote_tool,
    cancel_booking_tool,
    get_connecting_flight_quote_tool,
    book_connecting_flight_tool,
    get_reschedule_quote_tool,
    reschedule_booking_tool,
    check_flight_status_tool,
    get_my_bookings_tool,
    get_booking_details_tool,
    validate_coupon_tool,
    get_payment_methods_tool,
    process_payment_tool,
    get_my_loyalty_tool,
    get_refund_history_tool,
]


def create_booking_agent(user_context: str, user_memories: list[str] | None = None):
    llm = get_llm(streaming=True)

    prompt = BOOKING_AGENT_PROMPT.format(
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
