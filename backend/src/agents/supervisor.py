from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Literal

from .llm import get_llm
from .prompts import SUPERVISOR_PROMPT


class RouteDecision(BaseModel):
    next_agent: Literal["booking", "payment", "customer_service", "admin", "end"] = Field(
        description="Which specialist agent should handle this request"
    )
    reasoning: str = Field(description="Brief reasoning for the routing decision")


async def supervisor_node(state: dict) -> dict:
    llm = get_llm()
    structured_llm = llm.with_structured_output(RouteDecision)

    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
    decision = await structured_llm.ainvoke(messages)

    if decision.next_agent == "end":
        return {
            "active_agent": None,
            "messages": [AIMessage(content="Session ended. Feel free to start a new conversation anytime!")],
        }

    return {"active_agent": decision.next_agent}
