import pytest

from lick_finder.tools import LickFinderTools


@pytest.fixture
def tools(tmp_path):
    topics = tmp_path / "topics.txt"
    topics.write_text("# comment line\nBB King box blues lick lesson\n")
    return LickFinderTools(
        practice_log_path=tmp_path / "practice_log.json",
        topics_path=topics,
        search_fn=lambda query, level=None: [{"query": query, "level": level}],
    )


def save(tools, video_id, song="Hide Away", technique="intro", key="E", level="beginner"):
    return tools.save_lesson(video_id, song, technique, key, level)


def test_search_lessons_passes_query_and_level_through(tools):
    assert tools.search_lessons("hide away", level="beginner") == [
        {"query": "hide away", "level": "beginner"}
    ]
    assert tools.search_lessons("hide away") == [{"query": "hide away", "level": None}]


def test_save_lesson_stores_an_entry(tools):
    entry = save(tools, "abc")
    assert entry["video_id"] == "abc"
    assert entry["url"] == "https://www.youtube.com/watch?v=abc"
    assert entry["liked"] is False
    assert entry["view_count"] == 0
    assert entry["last_viewed"] is None
    assert tools.get_history() == [entry]


def test_save_lesson_rejects_a_duplicate(tools):
    save(tools, "abc")
    assert save(tools, "abc") == "already saved"
    assert len(tools.get_history()) == 1


def test_get_history_is_empty_without_a_log(tools):
    assert tools.get_history() == []


def test_get_history_filters_on_song_technique_and_key(tools):
    save(tools, "a", song="Hide Away", technique="intro", key="E")
    save(tools, "b", song="Pride and Joy", technique="shuffle", key="E")
    save(tools, "c", song="BB King box", technique="bending", key="G")

    assert [e["video_id"] for e in tools.get_history(filter="pride")] == ["b"]
    assert [e["video_id"] for e in tools.get_history(filter="BENDING")] == ["c"]
    assert sorted(e["video_id"] for e in tools.get_history(filter="e")) == ["a", "b", "c"]
    assert tools.get_history(filter="nothing like this") == []


def test_get_history_liked_only_and_limit(tools):
    for video_id in ("a", "b", "c"):
        save(tools, video_id)
    tools.like_lesson("b")

    assert [e["video_id"] for e in tools.get_history(liked_only=True)] == ["b"]
    assert len(tools.get_history(limit=2)) == 2


def test_get_history_is_newest_first(tools):
    save(tools, "old")
    save(tools, "new")
    entries = tools._read_log()
    entries[0]["saved_date"] = "2026-01-01"
    entries[1]["saved_date"] = "2026-06-01"
    tools._write_log(entries)

    assert [e["video_id"] for e in tools.get_history()] == ["new", "old"]


def test_open_lesson_counts_the_view(tools):
    save(tools, "abc")
    first = tools.open_lesson("abc")
    second = tools.open_lesson("abc")

    assert first == {"url": "https://www.youtube.com/watch?v=abc", "view_count": 1}
    assert second["view_count"] == 2
    assert tools.get_history()[0]["last_viewed"] is not None


def test_open_lesson_for_an_unsaved_video(tools):
    assert tools.open_lesson("missing") == "video missing is not in the practice history"


def test_like_lesson_marks_the_entry(tools):
    save(tools, "abc")
    assert tools.like_lesson("abc")["liked"] is True
    assert tools.get_history()[0]["liked"] is True


def test_like_lesson_for_an_unsaved_video(tools):
    assert tools.like_lesson("missing") == "video missing is not in the practice history"


def test_queue_topic_appends_a_new_topic(tools):
    assert tools.queue_topic("Magic Sam beginner licks") == "queued"
    assert "Magic Sam beginner licks" in tools.topics_path.read_text().splitlines()


def test_queue_topic_rejects_a_duplicate_ignoring_case(tools):
    assert tools.queue_topic("bb king BOX blues lick lesson") == "already queued"
    assert tools.topics_path.read_text().count("lick lesson") == 1


def test_queue_topic_does_not_treat_comments_as_topics(tools):
    assert tools.queue_topic("comment line") == "queued"


def test_change_saved_lesson_is_a_no_op(tools):
    save(tools, "abc")
    tools.like_lesson("abc")
    before = tools.practice_log_path.read_text()

    for action in ("delete", "edit", "unlike"):
        assert "Not supported" in tools.change_saved_lesson("abc", action)

    assert tools.practice_log_path.read_text() == before
