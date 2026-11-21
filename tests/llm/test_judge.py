"""LLM-judge tests: a second model grades the agent against written criteria.
They call real models, so they run only with `uv run pytest --llm`."""

import pytest

from lick_finder.agent import LickFinderTools
from lick_finder.business.lessons import LessonStore
from tests.llm.judge import assert_criteria, judge
from tests.llm.utils import run_agent_test

pytestmark = pytest.mark.llm

# Fake search results with known comments (no timestamps anywhere), so the
# judge has exact things to check the answer against.
BB_KING_RESULTS = [
    {
        "video_id": "fakebeg0001",
        "title": "Easy B.B. King Licks for Beginners",
        "channel": "Test Teacher",
        "url": "https://www.youtube.com/watch?v=fakebeg0001",
        "level": "beginner",
        "content": "We start with the minor pentatonic box and play the first lick very slowly, "
        "one string at a time, before speeding up.",
        "comments": [
            {"text": "Slow enough to follow, and the tab on screen helps a lot.", "likes": 14},
            {"text": "Great channel!!", "likes": 3},
        ],
    },
    {
        "video_id": "fakebeg0002",
        "title": "B.B. King Vibrato Basics",
        "channel": "Another Teacher",
        "url": "https://www.youtube.com/watch?v=fakebeg0002",
        "level": "beginner",
        "content": "Vibrato is the signature of B.B. King. Here is how to shake the string "
        "with your whole hand, starting with a single note.",
        "comments": [
            {"text": "Finally someone explains the wrist motion clearly.", "likes": 9},
        ],
    },
]

QUOTE_CRITERION = (
    "Any viewer comment quoted in the answer appears word for word in a comment in "
    "TOOL_RESULTS, with the same like count. If the answer quotes no comment, this passes."
)


@pytest.fixture
def bb_king_tools(tmp_path):
    topics = tmp_path / "topics.txt"
    topics.write_text("")
    levels = {r["video_id"]: {"level": r["level"]} for r in BB_KING_RESULTS}
    return LickFinderTools(
        practice_log_path=tmp_path / "practice_log.json",
        topics_path=topics,
        search_fn=lambda query, level=None: BB_KING_RESULTS,
        store=LessonStore(BB_KING_RESULTS, levels),
    )


@pytest.mark.asyncio
async def test_a_beginner_search_follows_the_agents_rules(agent_for, bb_king_tools):
    agent = agent_for(bb_king_tools)

    result = await run_agent_test(agent, "Easy BB King licks, I'm a beginner.")

    await assert_criteria(
        result,
        [
            "The agent called search_lessons with the argument level set to 'beginner'.",
            "The agent made no call to save_lesson, open_lesson, like_lesson or change_saved_lesson, "
            "because the user only asked to find lessons.",
            "Every lesson title named in the answer is one of the titles in TOOL_RESULTS. "
            "The answer names no lesson that is not in those results.",
            QUOTE_CRITERION,
            "The answer contains no timestamp such as 2:30 or 1:05:12, because no comment in "
            "TOOL_RESULTS gives one.",
        ],
    )


REAL_RESULTS = [str(r) for r in BB_KING_RESULTS]


@pytest.mark.asyncio
async def test_the_judge_passes_a_faithful_quote():
    feedback = await judge(
        [QUOTE_CRITERION],
        output='{"answer": "Try \'Easy B.B. King Licks for Beginners\'. One viewer says: '
        '\\"Slow enough to follow, and the tab on screen helps a lot.\\" (14 likes)"}',
        tool_calls=[
            "ToolCall(name='search_lessons', args={'query': 'BB King licks', 'level': 'beginner'})"
        ],
        tool_results=REAL_RESULTS,
    )

    assert feedback.criteria[0].passed, feedback.criteria[0].judgement


@pytest.mark.asyncio
async def test_the_judge_fails_an_invented_quote():
    feedback = await judge(
        [QUOTE_CRITERION],
        output='{"answer": "Try \'Easy B.B. King Licks for Beginners\'. One viewer says: '
        '\\"Best lick lesson ever, it changed my playing overnight.\\" (50 likes)"}',
        tool_calls=[
            "ToolCall(name='search_lessons', args={'query': 'BB King licks', 'level': 'beginner'})"
        ],
        tool_results=REAL_RESULTS,
    )

    assert not feedback.criteria[0].passed, feedback.criteria[0].judgement
