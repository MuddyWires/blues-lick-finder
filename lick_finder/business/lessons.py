"""Facts about lessons, looked up from the cache (no network, no OpenAI)."""

from functools import lru_cache

from ..integrations.levels import read_levels
from ..models import Chapter, LessonFacts, LessonPick, RecommendedLesson
from ..integrations.youtube_data import read_cache


class LessonStore:
    def __init__(self, documents, levels):
        self._docs = {d["video_id"]: d for d in documents}
        self._levels = levels

    def __contains__(self, video_id):
        return video_id in self._docs

    def facts(self, video_id):
        """The facts for a video, or None if it isn't in our data."""
        doc = self._docs.get(video_id)
        if doc is None:
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        chapters = []
        for c in doc.get("chapters") or []:
            start = int(c.get("start_time") or 0)
            chapters.append(Chapter(title=c.get("title") or "", start_sec=start,
                                    link=f"{url}&t={start}s"))

        return LessonFacts(
            video_id=video_id,
            url=url,
            title=doc.get("title") or "",
            channel=doc.get("channel") or "",
            duration_min=round((doc.get("duration_sec") or 0) / 60),
            views=doc.get("view_count"),
            level=self._levels.get(video_id, {}).get("level", "unclear"),
            has_transcript=bool(doc.get("transcript")),
            chapters=chapters,
        )

    def hydrate(self, picks: list[LessonPick]):
        """Turn the agent's picks into full lessons. Picks whose ID isn't in
        our data are dropped and returned separately, so the caller can flag them."""
        lessons, unknown = [], []
        for pick in picks:
            facts = self.facts(pick.video_id)
            if facts is None:
                unknown.append(pick.video_id)
            else:
                lessons.append(RecommendedLesson(facts=facts, pick=pick))
        return lessons, unknown


@lru_cache(maxsize=1)
def get_store():
    return LessonStore(read_cache(), read_levels())
