from pathlib import Path
from typing import Any, Literal

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart

from ..business import (
    InvalidTopic,
    LessonAlreadySaved,
    LessonNotInCatalog,
    LessonNotSaved,
    PracticeLog,
    TopicAlreadyQueued,
    TopicQueue,
)
from ..integrations.search import IndexNotBuilt, search
from ..paths import PRACTICE_LOG_PATH, TOPICS_PATH
from .results import ToolResult

# Policy for the agent, not a business rule: one question may search this many
# times. Nano tends to keep re-searching when results look off-topic.
MAX_SEARCHES_PER_QUESTION = 2


def searches_this_run(ctx: RunContext) -> int:
    """How many search_lessons calls came before this one in this question.

    Counts earlier responses and earlier calls in the same response (the model
    may request several at once), but not this call, later calls, or earlier
    questions in the conversation."""
    count = 0
    for m in ctx.messages:
        if not (isinstance(m, ModelResponse) and m.run_id == ctx.run_id):
            continue
        for p in m.parts:
            if isinstance(p, ToolCallPart) and p.tool_name == "search_lessons":
                if p.tool_call_id == ctx.tool_call_id:
                    return count
                count += 1
    return count


class LickFinderTools:
    """
    Searches stored blues lessons and manages a personal practice history.
    """

    def __init__(
        self,
        practice_log_path: Path = PRACTICE_LOG_PATH,
        topics_path: Path = TOPICS_PATH,
        search_fn=search,
        store=None,
    ):
        self.practice_log_path = practice_log_path
        self.topics_path = topics_path
        self._search = search_fn
        self.log = PracticeLog(practice_log_path, catalog=store)
        self.topics = TopicQueue(topics_path)

    def search_lessons(
        self, ctx: RunContext, query: str, level: str | None = None
    ) -> list[dict[str, Any]] | ToolResult:
        """
        Search the stored blues lesson videos. The first step for any "find
        me a lesson" request.

        Args:
            query: The song or technique to search for.
            level: Optional: "beginner", "intermediate" or "advanced". Omit
                unless the user asked for a level. Lessons whose level is
                unclear are still returned.
        """
        if searches_this_run(ctx) >= MAX_SEARCHES_PER_QUESTION:
            return ToolResult.of("search_limit", next_step="stop")
        try:
            return self._search(query, level=level)
        except IndexNotBuilt:
            return ToolResult.of("index_missing", next_step="stop")

    def save_lesson(
        self, video_id: str, song: str, technique: str, key: str, level: str
    ) -> ToolResult:
        """
        Save a lesson to the practice history. Call only when the user
        chooses a specific lesson (e.g. "I'll practice this one"), never
        automatically after a search. Rejects duplicates.

        Args:
            video_id: The video's video_id from search results.
            song: The song the lesson teaches, or "" if general.
            technique: The technique the lesson teaches, e.g. "string bending".
            key: The musical key, or "" if none is named.
            level: Your estimate of the lesson's level.
        """
        try:
            return ToolResult.of("ok", lesson=self.log.add(video_id, song, technique, key, level))
        except LessonNotInCatalog:
            return ToolResult.of("not_in_catalog", next_step="stop")
        except LessonAlreadySaved:
            return ToolResult.of("already_saved", next_step="stop")

    def get_history(self, filter: str | None = None, liked_only: bool = False, limit: int = 10):
        """
        List saved lessons, newest first. Use for questions about what's
        already saved, what to practice next, or to find a lesson to replay.

        Args:
            filter: Text to match against song, technique, or key. Omit to
                list everything.
            liked_only: Only return liked lessons.
            limit: Max entries to return.
        """
        return self.log.list(filter, liked_only, limit)

    def open_lesson(self, video_id: str) -> ToolResult:
        """Replay a saved lesson and record the view.

        Args:
            video_id: The video_id of the saved lesson to replay.
        """
        try:
            return ToolResult.of("ok", lesson=self.log.record_view(video_id))
        except LessonNotSaved:
            return ToolResult.of("not_saved", next_step="ask_user")

    def like_lesson(self, video_id: str) -> ToolResult:
        """Mark a saved lesson as liked.

        Args:
            video_id: The video_id of the saved lesson to like.
        """
        try:
            return ToolResult.of("ok", lesson=self.log.like(video_id))
        except LessonNotSaved:
            return ToolResult.of("not_saved", next_step="ask_user")

    def queue_topic(self, topic: str) -> ToolResult:
        """
        Queue a new search topic for the next data fetch, when
        search_lessons finds nothing relevant. Does not fetch immediately.

        Args:
            topic: The topic to queue, phrased like a YouTube search.
        """
        try:
            self.topics.add(topic)
        except InvalidTopic:
            return ToolResult.of("invalid_topic", next_step="stop")
        except TopicAlreadyQueued:
            return ToolResult.of("already_queued")
        return ToolResult.of("queued")

    def change_saved_lesson(
        self,
        video_id: str = "",
        action: Literal["delete", "edit", "unlike"] = "delete",
    ) -> ToolResult:
        """
        Delete a saved lesson, edit its details, or un-like it. NOT
        SUPPORTED YET: this changes nothing. Call it when the user asks for
        one of these, and follow its reply.

        Args:
            video_id: The video_id of the saved lesson. Leave empty if that
                lesson is not already in the conversation.
            action: "delete", "edit" or "unlike".
        """
        if not self.log.has(video_id):
            return ToolResult.of("not_saved", next_step="ask_user")
        return ToolResult.of("unsupported", next_step="stop")
