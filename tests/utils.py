import re
from dataclasses import dataclass
from typing import Any

from lick_finder.agent import AgentStreamRunner

from tests.cost_tracker import capture_usage


@dataclass
class ToolCall:
    name: str
    args: Any


def collect_tools(messages):
    tool_calls = []

    for m in messages:
        for p in m.parts:
            if p.part_kind != 'tool-call':
                continue

            if p.tool_name == 'final_result':
                continue

            tool_calls.append(ToolCall(p.tool_name, p.args))

    return tool_calls


@dataclass
class ToolReturn:
    name: str
    content: Any


def collect_tool_returns(messages):
    """What the tools returned, so a judge can check claims against it."""
    returns = []

    for m in messages:
        for p in m.parts:
            if p.part_kind != 'tool-return':
                continue

            if p.tool_name == 'final_result':
                continue

            returns.append(ToolReturn(p.tool_name, p.content))

    return returns


def get_model_name(agent):
    return f'{agent.model.system}:{agent.model.model_name}'


async def run_agent_test(agent, user_prompt, message_history=None):
    runner = AgentStreamRunner(agent)
    result = await runner.run(user_prompt, message_history)

    capture_usage(get_model_name(agent), result)

    return result


DENIAL = re.compile(
    r"can'?t|cannot|can ?not|not supported|isn'?t|aren'?t|unable|don'?t|didn'?t|"
    r"couldn'?t|wasn'?t|not in|no such|nothing was|unsupported",
    re.I,
)


def claims(answer, words):
    """True if the answer says it did something (e.g. 'deleted|removed')
    without also saying it couldn't or didn't."""
    answer = answer.replace("’", "'")  # models often write a curly apostrophe
    said_it = re.search(rf"\b({words})\b", answer, re.I)
    return bool(said_it) and not DENIAL.search(answer)
