"""Turn the model's structured answer into what the user sees.

The model only returns picks: a video_id and a reason. Everything else about a
lesson (title, channel, level, link) is copied from our own data by
LessonStore.hydrate(). A pick whose video_id is not in the data is dropped and
flagged, so a made-up or mistyped lesson never reaches the user as if it were real.
"""

from dataclasses import dataclass

from ..models import AgentResponse, RecommendedLesson, Reply

DROPPED_NOTE = (
    "Note: {n} recommended lesson(s) were left out because they are not in the lesson data."
)


@dataclass
class Presented:
    answer: str
    lessons: list[RecommendedLesson]
    dropped: list[str]  # video_ids that were not in the data


def present(response: Reply | AgentResponse, store) -> Presented:
    lessons, dropped = store.hydrate(getattr(response, "lessons", []))
    return Presented(response.answer, lessons, dropped)


def render_lessons(presented: Presented) -> str:
    """The recommended lessons as plain text, built from our data. Empty when
    there is nothing to show."""
    blocks = []
    for number, lesson in enumerate(presented.lessons, 1):
        facts = lesson.facts
        blocks.append(
            f"{number}. {facts.title}\n"
            f"   {facts.channel} · {facts.level} · {facts.duration_min} min\n"
            f"   {facts.url}\n"
            f"   Why: {lesson.pick.reason}"
        )
    if presented.dropped:
        blocks.append(DROPPED_NOTE.format(n=len(presented.dropped)))
    return "\n\n".join(blocks)


def render(presented: Presented) -> str:
    """Answer plus lessons, for places that show one block of text."""
    extra = render_lessons(presented)
    return f"{presented.answer}\n\n{extra}" if extra else presented.answer
