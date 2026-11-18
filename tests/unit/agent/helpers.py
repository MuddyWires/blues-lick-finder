"""Shared helpers for the tool tests."""

from types import SimpleNamespace

from pydantic_ai.messages import ModelResponse, ToolCallPart


def save(tools, video_id, song="Hide Away", technique="intro", key="E", level="beginner"):
    return tools.save_lesson(video_id, song, technique, key, level)


def fake_ctx(searches_this_run=0, searches_in_other_runs=0):
    """A stand-in RunContext: just the fields the search guard reads."""
    def call(run_id, n):
        return ModelResponse(
            parts=[ToolCallPart("search_lessons", {"query": "q"}, tool_call_id=f"{run_id}-{n}")],
            run_id=run_id,
        )
    messages = [call("other", i) for i in range(searches_in_other_runs)]
    messages += [call("now", i) for i in range(searches_this_run)]
    return SimpleNamespace(messages=messages, run_id="now", tool_call_id="current")


def parallel_ctx(position, size=3):
    """One response asking for `size` searches at once; the current call is the
    `position`-th (0-based)."""
    parts = [ToolCallPart("search_lessons", {"query": "q"}, tool_call_id=f"call-{i}") for i in range(size)]
    return SimpleNamespace(
        messages=[ModelResponse(parts=parts, run_id="now")],
        run_id="now",
        tool_call_id=f"call-{position}",
    )
