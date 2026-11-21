"""Data models for the agent's answer, the facts we know about a lesson, and
the labels inferred for it.

Three kinds of models:
- Filled by the agent (Quote, LessonPick, AgentResponse). The model reads the
  field descriptions, so they are instructions.
- Built by code from the cached data (Chapter, LessonFacts, RecommendedLesson).
  The agent never types these.
- Inferred once per video by a cheap LLM at ingestion and cached (LessonLabels).
  The descriptions steer the labelling model.
"""

from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced", "unclear"]

# Starting vocabularies. Review them against a labelling sample before the
# full run, then keep them fixed so filters and dropdowns stay clean.
Technique = Literal[
    "bending",
    "vibrato",
    "slide",
    "hammer-ons and pull-offs",
    "turnaround",
    "shuffle",
    "fingerpicking",
    "rhythm and comping",
    "licks and phrasing",
    "scales and boxes",
    "chords",
    "song or riff",
    "theory",
    "other",
]
Style = Literal[
    "Chicago",
    "Texas",
    "Delta",
    "Piedmont",
    "jump",
    "West Coast",
    "Memphis",
    "British",
    "country blues",
    "jazz blues",
    "rock blues",
    "other",
]


# ---- Filled by the agent (the model reads these descriptions) ----


class Quote(BaseModel):
    """A viewer comment quoted as evidence about the teaching."""

    text: str = Field(
        description=(
            "The comment, copied exactly word for word from a comment returned by "
            "search_lessons. Never paraphrase, shorten or fix it."
        )
    )
    likes: int = Field(description="The like count shown with that comment.")


class LessonPick(BaseModel):
    """One lesson the agent recommends. Return the ID only: facts are added by code."""

    video_id: str = Field(
        description=(
            "The video_id exactly as returned by search_lessons. Never invent or "
            "retype an ID from memory."
        )
    )
    reason: str = Field(
        description=(
            "One sentence on why this lesson teaches well, using the rubric "
            "(breakdown, demonstration, specifics, why, focus)."
        )
    )
    quote: Quote | None = Field(
        default=None,
        description=(
            "A viewer comment about the teaching (pace, clarity, tabs, mistakes). "
            "Null if no returned comment is about the teaching. Never invent one."
        ),
    )
    timestamp: str | None = Field(
        default=None,
        description=(
            "A position in the video as written (m:ss or h:mm:ss), only if a "
            "returned viewer comment states one. Null otherwise. Never guess."
        ),
    )


class Reply(BaseModel):
    """Use this for every reply that recommends no lesson: saving, history, a refusal, a question back to the user."""

    answer: str = Field(
        description=(
            "The conversational reply to the user, in plain text. Short: answer what was asked."
        )
    )


class AgentResponse(BaseModel):
    """Use this only when you recommend lessons from search results."""

    answer: str = Field(
        description=(
            "The conversational reply to the user, in plain text. Short: answer what was asked."
        )
    )
    lessons: list[LessonPick] = Field(
        default_factory=list,
        description=(
            "The lessons recommended in this reply, best first. Empty when "
            "nothing is recommended, e.g. history questions or nothing relevant."
        ),
    )


# ---- Built by code from the cache (documentation, not read by the agent) ----


class Chapter(BaseModel):
    title: str = Field(description="The chapter title from YouTube.")
    start_sec: int = Field(description="Where the chapter starts, in seconds.")
    link: str = Field(description="The video URL with &t=<start_sec>s appended.")


class LessonFacts(BaseModel):
    """Facts about a video copied from our data. The agent never types these."""

    video_id: str = Field(description="The YouTube video ID.")
    url: str = Field(description="https://www.youtube.com/watch?v=<video_id>.")
    title: str = Field(description="The video title.")
    channel: str = Field(description="The YouTube channel that published it.")
    duration_min: int = Field(description="Length in whole minutes.")
    views: int | None = Field(default=None, description="YouTube view count, if known.")
    level: Level = Field(
        description=(
            "Labelled once per video by a cheap LLM; 'unclear' when the evidence "
            "was thin (often no transcript)."
        )
    )
    has_transcript: bool = Field(
        description=("False means the video can't be found by transcript search.")
    )
    chapters: list[Chapter] = Field(
        default_factory=list,
        description=("YouTube chapters with links. Empty when the video has none."),
    )


# ---- Inferred once per video by a cheap LLM, then cached ----


class LessonLabels(BaseModel):
    """Labels for one video, from its title, description, transcript and comments."""

    lesson_type: Literal["lesson", "performance", "gear", "other"] = Field(
        description=(
            "'lesson' if it teaches how to play something; 'performance' for a "
            "live or recorded play-through with no teaching; 'gear' for equipment "
            "demos or reviews; 'other' otherwise."
        )
    )
    technique: list[Technique] = Field(
        default_factory=list,
        description=(
            "What is taught, picked only from the allowed list. Several are fine. Empty if unclear."
        ),
    )
    style: Style | None = Field(
        default=None,
        description=(
            "The blues style if stated or obvious, picked from the allowed list. Null if unclear."
        ),
    )
    song: str | None = Field(
        default=None,
        description=(
            "The song being taught, e.g. 'Hide Away'. Null if the lesson isn't "
            "about one specific song."
        ),
    )
    artist: str | None = Field(
        default=None,
        description=(
            "The artist whose song or style is taught, e.g. 'Freddie King'. Null "
            "if not clearly stated."
        ),
    )
    key: str | None = Field(
        default=None,
        pattern=r"^[A-G][#b]?m?$",
        description=(
            "The musical key, only if the title, description or transcript states "
            "exactly one key outright (e.g. 'in the key of A'). Format: a note name "
            "with optional # or b, and 'm' for minor: A, Bb, F#, Em. Null if it "
            "isn't stated, if several keys are covered, or if you would have to "
            "guess. Never guess."
        ),
    )
    evidence: str | None = Field(
        default=None,
        description=(
            "A short snippet copied exactly from the title, description or "
            "transcript that supports song, artist or key. Required whenever key "
            "is set. Null if none."
        ),
    )


class RecommendedLesson(BaseModel):
    """What the CLI, API and tests work with: facts + labels + the agent's pick."""

    facts: LessonFacts = Field(description="Facts about the video, copied from our data.")
    labels: LessonLabels | None = Field(
        default=None, description=("Present once the labelling pass has run for this video.")
    )
    pick: LessonPick = Field(description="The agent's reason, quote and timestamp for this lesson.")
