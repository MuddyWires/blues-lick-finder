"""What the thin layer returns: a typed, machine-readable result.

`status` and `next_step` come from fixed sets, so a program (or another agent)
can branch on them. `message` is a constant for the model to read.
"""

from typing import Literal

from pydantic import BaseModel

from .tool_messages import MESSAGES

Status = Literal[
    "ok",
    "already_saved",
    "not_in_catalog",
    "not_saved",
    "queued",
    "already_queued",
    "invalid_topic",
    "search_limit",
    "unsupported",
    "index_missing",
]
NextStep = Literal["none", "ask_user", "stop"]


class SavedLesson(BaseModel):
    video_id: str
    url: str
    song: str
    technique: str
    key: str
    level: str
    saved_date: str
    liked: bool
    view_count: int
    last_viewed: str | None = None


class ToolResult(BaseModel):
    status: Status
    next_step: NextStep = "none"
    message: str
    lesson: SavedLesson | None = None

    @classmethod
    def of(cls, status: Status, next_step: NextStep = "none", lesson: dict | None = None):
        """Build a result, attaching the fixed message for the status."""
        return cls(
            status=status,
            next_step=next_step,
            message=MESSAGES[status],
            lesson=SavedLesson(**lesson) if lesson else None,
        )
