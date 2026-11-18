"""The business layer, tested with no model and no API."""

import pytest

from lick_finder.business import (
    LessonAlreadySaved,
    LessonNotInCatalog,
    LessonNotSaved,
    PracticeLog,
)


@pytest.fixture
def log(tmp_path):
    return PracticeLog(tmp_path / "log.json", catalog={"a", "b", "c"})


def add(log, video_id, song="Hide Away", technique="intro", key="E", level="beginner"):
    return log.add(video_id, song, technique, key, level)


def test_add_stores_an_entry(log):
    entry = add(log, "a")

    assert entry["video_id"] == "a"
    assert entry["liked"] is False
    assert entry["view_count"] == 0
    assert log.has("a")


def test_add_rejects_a_video_that_is_not_in_the_catalog(log):
    with pytest.raises(LessonNotInCatalog):
        add(log, "zzz")
    assert not log.has("zzz")


def test_add_rejects_duplicates(log):
    add(log, "a")

    with pytest.raises(LessonAlreadySaved):
        add(log, "a")
    assert len(log.list()) == 1


def test_list_is_newest_first(log):
    add(log, "a")
    add(log, "b")
    entries = log._read()
    entries[0]["saved_date"] = "2026-01-01"
    entries[1]["saved_date"] = "2026-06-01"
    log._write(entries)

    assert [e["video_id"] for e in log.list()] == ["b", "a"]


def test_list_filters_on_song_technique_and_key(log):
    add(log, "a", song="Hide Away", key="A")
    add(log, "b", song="Pride and Joy", key="E")

    assert [e["video_id"] for e in log.list(filter="pride")] == ["b"]
    assert [e["video_id"] for e in log.list(filter="hide")] == ["a"]


def test_list_can_return_only_liked_lessons_and_respects_the_limit(log):
    add(log, "a")
    add(log, "b")
    log.like("b")

    assert [e["video_id"] for e in log.list(liked_only=True)] == ["b"]
    assert len(log.list(limit=1)) == 1


def test_record_view_counts_the_view(log):
    add(log, "a")

    entry = log.record_view("a")

    assert entry["view_count"] == 1
    assert entry["last_viewed"] is not None


def test_like_marks_the_lesson_as_liked(log):
    add(log, "a")

    assert log.like("a")["liked"] is True


@pytest.mark.parametrize("operation", ["record_view", "like"])
def test_operations_on_an_unsaved_lesson_raise(log, operation):
    with pytest.raises(LessonNotSaved):
        getattr(log, operation)("a")


def test_a_missing_file_is_an_empty_log(tmp_path):
    assert PracticeLog(tmp_path / "nope.json", catalog=set()).list() == []

