"""LangGraph orchestrator for the Palm Logistics AI assistant."""

import os
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.agent_tools import (  # noqa: E402
    fetch_corridor_conditions,
    query_logistics_db,
    search_compliance_sop,
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


OPENROUTER_API_KEY = _required_env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).strip()
AGENT_MODEL = os.getenv("AGENT_MODEL", "deepseek/deepseek-v4-pro").strip()


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ---------------------------------------------------------------------------
# Model and operational instructions
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "system_prompt.txt"


def _load_system_instructions(prompt_path: Path) -> str:
    """Load the required external prompt and reject a missing/empty file."""
    try:
        instructions = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(
            f"Unable to load the system prompt from {prompt_path}"
        ) from exc

    if not instructions:
        raise RuntimeError(f"System prompt is empty: {prompt_path}")
    return instructions


SYSTEM_INSTRUCTIONS = _load_system_instructions(SYSTEM_PROMPT_PATH)

SYSTEM_MESSAGE = SystemMessage(content=SYSTEM_INSTRUCTIONS)

llm = ChatOpenAI(
    model=AGENT_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    temperature=0,
    max_tokens=2048,
    timeout=60,
    max_retries=2,
    default_headers={"X-Title": "Palm Logistics AI Assistant"},
)

palm_tools = [
    query_logistics_db,
    fetch_corridor_conditions,
    search_compliance_sop,
]
llm_with_tools = llm.bind_tools(palm_tools)


# ---------------------------------------------------------------------------
# LangGraph workflow
# ---------------------------------------------------------------------------
def reasoning_node(state: AgentState) -> dict[str, list[BaseMessage]]:
    """Let the model answer or choose the next evidence-gathering tool."""
    response = llm_with_tools.invoke([SYSTEM_MESSAGE, *state["messages"]])
    return {"messages": [response]}


graph_builder = StateGraph(AgentState)
graph_builder.add_node("reasoner", reasoning_node)
graph_builder.add_node("tools", ToolNode(palm_tools))
graph_builder.add_edge(START, "reasoner")
graph_builder.add_conditional_edges(
    "reasoner",
    tools_condition,
    {"tools": "tools", END: END},
)
graph_builder.add_edge("tools", "reasoner")

palm_agent = graph_builder.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Local chat test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Palm Logistics AI Assistant")
    print(f"Model: {AGENT_MODEL} via OpenRouter")
    print("Type 'exit' or 'quit' to close.")
    print("=" * 60)

    thread_config = {"configurable": {"thread_id": "palm-logistics-local-test"}}

    while True:
        try:
            user_input = input("\nDispatcher > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession closed.")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Session closed.")
            break
        if not user_input:
            continue

        try:
            events = palm_agent.stream(
                {"messages": [("user", user_input)]},
                config=thread_config,
                stream_mode="updates",
            )

            for event in events:
                for node_name, node_state in event.items():
                    if node_name == "tools":
                        print("   [Tools] Evidence retrieved.")
                    elif node_name == "reasoner":
                        latest_message = node_state["messages"][-1]
                        if latest_message.content:
                            print(f"\nPalm Logistics Agent:\n{latest_message.content}")
        except Exception as exc:
            print(f"\nAgent request failed: {exc}")
