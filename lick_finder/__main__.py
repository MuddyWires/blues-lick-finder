"""Interactive chat with the lick finder: `uv run python -m lick_finder`."""

import asyncio

from .agent import AgentStreamRunner, LickFinderAgentConfig, create_agent
from .tools import LickFinderTools


async def chat():
    runner = AgentStreamRunner(create_agent(LickFinderAgentConfig(), LickFinderTools()))
    history = []

    print("Blues Lick Finder. Type a question, or 'quit' (or Ctrl-D) to exit.")
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
        history = result.all_messages()
        print()


if __name__ == "__main__":
    asyncio.run(chat())
