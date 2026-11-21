"""The structured answer: recommended lessons are checked against the lesson data.

These run a real pydantic-ai Agent with a FunctionModel (a scripted model), so
the output validator, the retry and the output schema are the real ones. No
network, no API key.
"""

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from lick_finder.agent import LickFinderAgentConfig, create_agent, present, render
from lick_finder.agent.agent import UNKNOWN_LESSON_MESSAGE

pytestmark = pytest.mark.asyncio


def pick(video_id, reason="Clear breakdown."):
    return {"video_id": video_id, "reason": reason}


def scripted(*replies):
    """A model that answers with each reply in turn (the last one repeats) and
    records every request it was sent. A reply with `lessons` uses the
    AgentResponse output, any other reply uses the plain Reply output."""
    requests = []

    def respond(messages, info):
        requests.append(messages)
        reply = replies[min(len(requests), len(replies)) - 1]
        wanted = "AgentResponse" if "lessons" in reply else "Reply"
        tool = next(t for t in info.output_tools if t.name.endswith(wanted))
        return ModelResponse(parts=[ToolCallPart(tool.name, reply)])

    return FunctionModel(respond), requests


async def ask(tools, *replies):
    model, requests = scripted(*replies)
    agent = create_agent(LickFinderAgentConfig(model=model), tools)
    result = await agent.run("best lesson for hide away?")
    return result, requests


def retry_messages(requests):
    """The text the model was shown when its output was sent back for a retry.
    Older pydantic-ai versions send it as a RetryPromptPart, newer ones as a
    ToolReturnPart marked as a retry; accept both."""
    return [
        part.content
        for request in requests
        for message in request
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, RetryPromptPart) or getattr(part, "outcome", None) == "retried"
    ]


async def test_known_lessons_are_filled_in_from_our_data(tools):
    result, requests = await ask(tools, {"answer": "Try this one.", "lessons": [pick("abc")]})

    shown = present(result.output, tools.lesson_store())

    assert len(requests) == 1  # no retry needed
    assert [lesson.facts.video_id for lesson in shown.lessons] == ["abc"]
    assert shown.dropped == []
    text = render(shown)
    assert "https://www.youtube.com/watch?v=abc" in text  # the link comes from our data
    assert "Why: Clear breakdown." in text


async def test_an_unknown_id_makes_the_model_retry_once_with_a_fixed_message(tools):
    result, requests = await ask(
        tools,
        {"answer": "Try this.", "lessons": [pick("made-up-id")]},
        {"answer": "Try this.", "lessons": [pick("abc")]},
    )

    shown = present(result.output, tools.lesson_store())

    assert len(requests) == 2
    assert retry_messages(requests) == [UNKNOWN_LESSON_MESSAGE]
    assert "made-up-id" not in UNKNOWN_LESSON_MESSAGE  # the model's own text is never echoed back
    assert [lesson.facts.video_id for lesson in shown.lessons] == ["abc"]
    assert shown.dropped == []


async def test_an_id_that_is_still_unknown_after_the_retry_is_dropped_and_flagged(tools):
    result, requests = await ask(
        tools, {"answer": "Try these.", "lessons": [pick("abc"), pick("made-up-id")]}
    )

    shown = present(result.output, tools.lesson_store())  # must not raise

    assert len(requests) == 2  # one retry, then it gives up asking
    assert [lesson.facts.video_id for lesson in shown.lessons] == ["abc"]
    assert shown.dropped == ["made-up-id"]
    text = render(shown)
    assert "1 recommended lesson(s) were left out" in text
    assert "made-up-id" not in text  # the invented id is never shown


async def test_an_answer_with_no_lessons_needs_no_checking_or_retry(tools):
    result, requests = await ask(tools, {"answer": "You have 4 saved lessons."})

    shown = present(result.output, tools.lesson_store())

    assert len(requests) == 1
    assert shown.lessons == [] and shown.dropped == []
    assert render(shown) == "You have 4 saved lessons."


async def test_the_model_can_choose_between_a_plain_reply_and_a_reply_with_lessons(tools):
    model, _ = scripted({"answer": "x"})
    agent = create_agent(LickFinderAgentConfig(model=model), tools)

    result = await agent.run("hi")

    assert type(result.output).__name__ == "Reply"  # no `lessons` field to fill for a refusal
