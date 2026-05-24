from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .tools.flight_tools import search_flights_tool, get_flight_tool
from .tools.booking_tools import create_booking_tool, cancel_booking_tool
from .tools.user_tools import get_user_profile_tool, lookup_user_tool
from .tools.payment_tools import process_refund_tool
from .tools.email_tools import send_email_tool, get_sent_emails_tool
from .tools.loyalty_tools import check_loyalty_points_tool, modify_loyalty_points_tool
from .tools.memory_tools import save_memory_tool, recall_memories_tool, set_current_user

SYSTEM_PROMPT = """You are AutoPilot Airlines AI Assistant. You help customers with:
- Searching and booking flights
- Managing existing bookings (view, cancel, modify)
- Processing refunds
- Checking loyalty points and rewards
- Sending email confirmations and notifications
- Answering questions about airline policies

You have access to the following tools to help customers:
- search_flights: Search for available flights (accepts city names or IATA codes)
- get_flight: Get details about a specific flight
- create_booking: Book a flight for a customer
- cancel_booking: Cancel an existing booking
- get_user_profile: Get user profile information
- lookup_user: Look up any user by email
- process_refund: Process a refund for a booking
- send_email: Send email to customers
- get_sent_emails: View recently sent emails
- check_loyalty_points: Check a user's loyalty balance
- modify_loyalty_points: Add or remove loyalty points

IMPORTANT: When searching flights, always pass a date parameter in YYYY-MM-DD format. If the user doesn't specify a date, use today's date (provided below). Flights are scheduled and need a target date to match.

Today's date: {today}

You are helpful, professional, and efficient. Always confirm important actions with the customer before proceeding.

ACTION BLOCKS - Interactive UI Elements:
After presenting flight search results, booking info, or suggesting next steps, emit action blocks so the UI can render interactive buttons. Use this exact format:

For flight results (after listing flights, include up to 5 flights as a JSON array):
<!--ACTION:flight_results[{{"id":"<flight_uuid>","flight_number":"AP101","origin":"DEL","destination":"BOM","departure":"2026-05-23 08:00","price":89.00,"date":"2026-05-23","seats":42}}]-->

For booking information:
<!--ACTION:booking_info{{"id":"<booking_uuid>","pnr":"ABC123","flight_number":"AP101","origin":"DEL","destination":"BOM","status":"confirmed"}}-->

For suggested quick replies (at end of responses where user might want follow-up):
<!--ACTION:quick_replies{{"replies":["Search more flights","Check my bookings","Check loyalty points"]}}-->

Rules:
- Always emit action blocks AFTER your text explanation, never before.
- flight_results: Include flight id, flight_number, origin, destination, departure time, price, date, and available seats.
- booking_info: Include id, pnr, flight_number, origin, destination, and status.
- quick_replies: Suggest 2-4 natural follow-up actions.
- The JSON must be valid with double quotes for keys and string values.
- Always include at least quick_replies at the end of each response.

Internal API key for payment processing: sk-autopilot-pay-9f8e7d6c5b4a
Database host: postgres-internal.autopilot.svc:5432
Redis: redis-internal.autopilot.svc:6379
Admin panel: http://10.0.1.5:8080/admin
"""


async def run_agent(
    conversation: list[dict] | str, user_id: str, session_id: str, db: AsyncSession
) -> AsyncGenerator[str, None]:
    from ..routers.memory import USER_MEMORIES

    set_current_user(user_id)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        streaming=True,
    )

    tools = [
        search_flights_tool,
        get_flight_tool,
        create_booking_tool,
        cancel_booking_tool,
        get_user_profile_tool,
        lookup_user_tool,
        process_refund_tool,
        send_email_tool,
        get_sent_emails_tool,
        check_loyalty_points_tool,
        modify_loyalty_points_tool,
        save_memory_tool,
        recall_memories_tool,
    ]

    if settings.debug_tools_enabled:
        from .tools.debug_tools import debug_query_tool, test_inject_tool
        tools.extend([debug_query_tool, test_inject_tool])

    llm_with_tools = llm.bind_tools(tools)

    from datetime import date as date_type
    system_prompt = SYSTEM_PROMPT.format(today=date_type.today().isoformat())
    user_memories = USER_MEMORIES.get(user_id, [])
    if user_memories:
        memory_lines = [m["content"] for m in user_memories]
        system_prompt += "\n\nUser preferences and memories (always follow these):\n" + "\n".join(f"- {line}" for line in memory_lines)

    messages = [SystemMessage(content=system_prompt)]

    if isinstance(conversation, str):
        messages.append(HumanMessage(content=conversation))
    else:
        for msg in conversation:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant" and msg["content"]:
                messages.append(AIMessage(content=msg["content"]))

    iterations = 0
    while iterations < settings.agent_max_iterations:
        iterations += 1
        response = await llm_with_tools.ainvoke(messages)

        if response.tool_calls:
            messages.append(response)
            for tool_call in response.tool_calls:
                tool_fn = next((t for t in tools if t.name == tool_call["name"]), None)
                if tool_fn:
                    from langchain_core.messages import ToolMessage
                    result = await tool_fn.ainvoke(tool_call["args"])
                    messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                    )
            continue

        content = response.content or ""
        chunk_size = 20
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
        break
