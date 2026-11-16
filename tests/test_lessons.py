from lick_finder.lessons import LessonStore
from lick_finder.models import LessonPick

DOCS = [
    {
        "video_id": "full",
        "title": "Hide Away intro",
        "channel": "Some Teacher",
        "duration_sec": 600,
        "view_count": 1234,
        "transcript": "so the first lick goes like this",
        "chapters": [
            {"start_time": 0, "title": "Intro"},
            {"start_time": 95, "title": "The turnaround"},
        ],
    },
    {"video_id": "bare", "title": "No extras", "channel": "Other", "duration_sec": None,
     "transcript": None},
]
LEVELS = {"full": {"level": "beginner", "reason": "slow"}}


def store():
    return LessonStore(DOCS, LEVELS)


def pick(video_id):
    return LessonPick(video_id=video_id, reason="Clear breakdown.")


def test_facts_are_copied_from_the_data():
    facts = store().facts("full")
    assert facts.url == "https://www.youtube.com/watch?v=full"
    assert (facts.title, facts.channel) == ("Hide Away intro", "Some Teacher")
    assert facts.duration_min == 10
    assert facts.views == 1234
    assert facts.level == "beginner"
    assert facts.has_transcript is True


def test_chapters_get_timestamped_links():
    chapters = store().facts("full").chapters
    assert [c.title for c in chapters] == ["Intro", "The turnaround"]
    assert chapters[1].start_sec == 95
    assert chapters[1].link == "https://www.youtube.com/watch?v=full&t=95s"


def test_missing_data_gets_safe_defaults():
    facts = store().facts("bare")
    assert facts.level == "unclear"
    assert facts.has_transcript is False
    assert facts.views is None
    assert facts.duration_min == 0
    assert facts.chapters == []


def test_an_unknown_video_has_no_facts():
    assert store().facts("nope") is None


def test_contains_checks_the_data():
    assert "full" in store()
    assert "nope" not in store()


def test_hydrate_keeps_order_and_separates_unknown_ids():
    lessons, unknown = store().hydrate([pick("bare"), pick("made-up"), pick("full")])

    assert [l.facts.video_id for l in lessons] == ["bare", "full"]
    assert unknown == ["made-up"]
    assert lessons[1].pick.reason == "Clear breakdown."
    assert lessons[0].labels is None
