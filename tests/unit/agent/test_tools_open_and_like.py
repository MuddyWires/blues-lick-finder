"""open_lesson and like_lesson."""

from .helpers import save


def test_open_lesson_counts_the_view(tools):
    save(tools, "abc")
    first = tools.open_lesson("abc").lesson
    second = tools.open_lesson("abc").lesson

    assert first.url == "https://www.youtube.com/watch?v=abc"
    assert first.view_count == 1
    assert second.view_count == 2
    assert tools.get_history()[0]["last_viewed"] is not None


def test_open_lesson_for_an_unsaved_video(tools):
    assert tools.open_lesson("missing").status == "not_saved"


def test_like_lesson_marks_the_entry(tools):
    save(tools, "abc")
    assert tools.like_lesson("abc").lesson.liked is True
    assert tools.get_history()[0]["liked"] is True


def test_like_lesson_for_an_unsaved_video(tools):
    assert tools.like_lesson("missing").status == "not_saved"
