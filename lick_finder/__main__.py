"""Interactive chat with the lick finder: `uv run python -m lick_finder`."""

import asyncio

import logfire

from .agent import AgentStreamRunner, LickFinderAgentConfig, create_agent
from .cost import capture_usage, display_total_usage, total_cost
from .monitoring import TRACE_URL, setup_monitoring
from .tools import LickFinderTools
from .turn import format_summary, turn_summary


async def chat():
    setup_monitoring()
    config = LickFinderAgentConfig()
    runner = AgentStreamRunner(create_agent(config, LickFinderTools()))
    history = []

    print("Blues Lick Finder. Type a question, or 'quit' (or Ctrl-D) to exit.")
    with logfire.span("chat session") as session:
        while True:
            try:
                question = input("\n> ").strip()
            except EOFError:
                break
            if question in ("quit", "exit"):
                break
            if not question:
                continue

            result = await runner.run(question, message_history=history)
            capture_usage(config.model, result)
            history = result.all_messages()
            print(f"\n[{format_summary(turn_summary(result, config.model))}]")

        session.set_attribute("cost_usd", total_cost())
        trace_id = format(session.get_span_context().trace_id, "032x")
    print(f"Trace: {TRACE_URL}?q=trace_id%3D'{trace_id}'")
    display_total_usage()


if __name__ == "__main__":
    asyncio.run(chat())
