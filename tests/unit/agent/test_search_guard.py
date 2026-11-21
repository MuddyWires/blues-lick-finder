"""The cap on searches per question."""

import pytest

from lick_finder.agent.results import ToolResult
from lick_finder.agent.tools import MAX_SEARCHES_PER_QUESTION, searches_this_run

from .helpers import fake_ctx, parallel_ctx


def test_search_lessons_passes_query_and_level_through(tools):
    assert tools.search_lessons(fake_ctx(), "hide away", level="beginner") == [
        {"query": "hide away", "level": "beginner"}
    ]
    assert tools.search_lessons(fake_ctx(), "hide away") == [{"query": "hide away", "level": None}]


def test_search_is_refused_after_the_limit_for_this_question(tools):
    ctx = fake_ctx(searches_this_run=MAX_SEARCHES_PER_QUESTION)

    result = tools.search_lessons(ctx, "jazz chords")

    assert (result.status, result.next_step) == ("search_limit", "stop")


def test_searches_just_under_the_limit_still_run(tools):
    ctx = fake_ctx(searches_this_run=MAX_SEARCHES_PER_QUESTION - 1)

    assert tools.search_lessons(ctx, "jazz chords") == [{"query": "jazz chords", "level": None}]


def test_searches_from_earlier_questions_do_not_count(tools):
    ctx = fake_ctx(searches_in_other_runs=10)

    assert searches_this_run(ctx) == 0
    assert tools.search_lessons(ctx, "hide away")


@pytest.mark.parametrize("position", [0, 1, 2])
def test_a_search_counts_only_the_calls_before_it_in_the_same_response(position):
    assert searches_this_run(parallel_ctx(position)) == position


def test_only_the_first_searches_run_when_several_are_requested_at_once(tools):
    results = [tools.search_lessons(parallel_ctx(i), "q") for i in range(3)]

    ran = [not isinstance(r, ToolResult) for r in results]
    assert ran == [True, True, False]   # MAX_SEARCHES_PER_QUESTION is 2


def test_a_missing_index_becomes_a_fixed_message_not_a_crash(tmp_path):
    from lick_finder.agent import LickFinderTools
    from lick_finder.integrations.search import IndexNotBuilt

    def broken_search(query, level=None):
        raise IndexNotBuilt("2535 of 2535 chunks have no embedding")

    topics = tmp_path / "topics.txt"
    topics.write_text("")
    tools = LickFinderTools(practice_log_path=tmp_path / "log.json", topics_path=topics,
                            search_fn=broken_search, store={})

    result = tools.search_lessons(fake_ctx(), "hide away")

    assert (result.status, result.next_step) == ("index_missing", "stop")
    assert "2535" not in result.message  # internal details stay out of the reply
