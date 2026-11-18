"""The topic queue, tested with no model and no API."""

import pytest

from lick_finder.business import InvalidTopic, TopicAlreadyQueued, TopicQueue


@pytest.fixture
def queue(tmp_path):
    path = tmp_path / "topics.txt"
    path.write_text("# comment line\nBB King box blues lick lesson\n")
    return TopicQueue(path)


def lines(queue):
    return queue.path.read_text().splitlines()


def test_add_appends_a_new_topic(queue):
    queue.add("Magic Sam beginner licks")

    assert "Magic Sam beginner licks" in lines(queue)


def test_add_strips_surrounding_whitespace(queue):
    queue.add("  Magic Sam beginner licks \n")

    assert lines(queue)[-1] == "Magic Sam beginner licks"


def test_add_rejects_a_duplicate_ignoring_case(queue):
    with pytest.raises(TopicAlreadyQueued):
        queue.add("bb king BOX blues lick lesson")

    assert queue.path.read_text().count("lick lesson") == 1


def test_a_comment_line_is_not_a_queued_topic(queue):
    queue.add("comment line")

    assert lines(queue)[-1] == "comment line"


@pytest.mark.parametrize("topic", [
    "",
    "   ",
    "two\nlines",
    "# a comment",
    "channel:@somebody",
    "CHANNEL:UC123",
    "tab\tseparated",
    "x" * 101,
])
def test_add_rejects_anything_that_is_not_one_plain_search_phrase(queue, topic):
    before = queue.path.read_text()

    with pytest.raises(InvalidTopic):
        queue.add(topic)

    assert queue.path.read_text() == before
