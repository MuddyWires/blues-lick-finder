import pytest

from lick_finder.agent import LickFinderTools
from lick_finder.business.lessons import LessonStore

KNOWN_IDS = ["abc", "a", "b", "c", "old", "new"]


# Overrides the root `tools` fixture: these tests use a fake search and a
# topics file with one existing topic.
@pytest.fixture
def tools(tmp_path):
    topics = tmp_path / "topics.txt"
    topics.write_text("# comment line\nBB King box blues lick lesson\n")
    return LickFinderTools(
        practice_log_path=tmp_path / "practice_log.json",
        topics_path=topics,
        search_fn=lambda query, level=None: [{"query": query, "level": level}],
        store=LessonStore([{"video_id": v} for v in KNOWN_IDS], {}),
    )
