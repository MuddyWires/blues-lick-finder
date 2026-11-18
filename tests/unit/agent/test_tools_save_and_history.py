"""save_lesson and get_history, the thin layer over PracticeLog."""

from .helpers import save


def test_save_lesson_stores_an_entry(tools):
    result = save(tools, "abc")
    assert result.status == "ok"
    entry = result.lesson
    assert entry.video_id == "abc"
    assert entry.url == "https://www.youtube.com/watch?v=abc"
    assert entry.liked is False
    assert entry.view_count == 0
    assert entry.last_viewed is None
    assert tools.get_history() == [entry.model_dump()]


def test_save_lesson_rejects_a_duplicate(tools):
    save(tools, "abc")
    assert save(tools, "abc").status == "already_saved"
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
    entries = tools.log._read()
    entries[0]["saved_date"] = "2026-01-01"
    entries[1]["saved_date"] = "2026-06-01"
    tools.log._write(entries)

    assert [e["video_id"] for e in tools.get_history()] == ["new", "old"]


def test_save_lesson_rejects_an_id_that_is_not_in_the_lesson_data(tools):
    result = save(tools, "xyz123")

    assert result.status == "not_in_catalog"
    assert "xyz123" not in result.message
    assert tools.get_history() == []
    assert not tools.practice_log_path.exists()


def test_save_lesson_still_saves_a_known_id(tools):
    assert save(tools, "abc").lesson.video_id == "abc"
