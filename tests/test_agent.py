"""Agent-level tests: they call a real model, so they are skipped unless you
run `uv run pytest --llm`. Each scenario runs REPEATS times because model
answers vary. We assert on which tools ran and on the practice log, and only
loosely on the wording."""

import pytest

from tests.utils import claims, collect_tools, run_agent_test

REPEATS = 3

pytestmark = pytest.mark.llm


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", range(REPEATS))
async def test_agent_does_not_save_an_id_that_is_not_in_the_lesson_data(agent_for, tools, attempt):
    agent = agent_for(tools)

    result = await run_agent_test(agent, "Save the lesson with video id xyz123 to my practice log.")

    assert tools.get_history() == []
    assert not claims(result.output.answer, "saved|added|logged")


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", range(REPEATS))
async def test_agent_says_deleting_is_not_supported(agent_for, saved_tools, attempt):
    agent = agent_for(saved_tools)
    before = saved_tools.practice_log_path.read_text()

    result = await run_agent_test(agent, "Delete the BB King box lesson from my history.")

    tool_names = [call.name for call in collect_tools(result.new_messages())]
    assert "change_saved_lesson" in tool_names

    assert saved_tools.practice_log_path.read_text() == before
    assert not claims(result.output.answer, "deleted|removed|erased")


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", range(REPEATS))
async def test_agent_says_unliking_is_not_supported(agent_for, saved_tools, attempt):
    agent = agent_for(saved_tools)

    first = await run_agent_test(agent, "What have I liked?")
    before = saved_tools.practice_log_path.read_text()

    second = await run_agent_test(agent, "Unlike the first one.", first.all_messages())

    tool_names = [call.name for call in collect_tools(second.new_messages())]
    assert "change_saved_lesson" in tool_names

    assert saved_tools.practice_log_path.read_text() == before
    assert not claims(second.output.answer, "unliked|removed")
