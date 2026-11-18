import pytest
from pydantic import ValidationError

from lick_finder import models
from lick_finder.models import AgentResponse, LessonLabels, LessonPick, Quote

ALL_MODELS = [
    models.Quote, models.LessonPick, models.AgentResponse, models.Chapter,
    models.LessonFacts, models.LessonLabels, models.RecommendedLesson,
]


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_every_field_has_a_description(model):
    missing = [name for name, field in model.model_fields.items() if not field.description]
    assert missing == []


def test_the_agent_sees_the_field_descriptions_in_its_schema():
    schema = AgentResponse.model_json_schema()
    assert schema["properties"]["answer"]["description"]
    assert "word for word" in schema["$defs"]["Quote"]["properties"]["text"]["description"]


def test_an_answer_with_no_lessons_is_valid():
    assert AgentResponse(answer="Nothing relevant found.").lessons == []


def test_a_pick_needs_only_an_id_and_a_reason():
    pick = LessonPick(video_id="abc", reason="Slow, clear breakdown.")
    assert pick.quote is None and pick.timestamp is None


def test_a_quote_keeps_its_like_count():
    assert Quote(text="Great pace", likes=12).likes == 12


@pytest.mark.parametrize("key", ["A", "Bb", "F#", "Em", "C#m"])
def test_valid_keys_are_accepted(key):
    assert LessonLabels(lesson_type="lesson", key=key).key == key


@pytest.mark.parametrize("key", ["H", "A major", "key of A", "a", "Ab#", ""])
def test_invalid_keys_are_rejected(key):
    with pytest.raises(ValidationError):
        LessonLabels(lesson_type="lesson", key=key)


def test_technique_and_style_must_come_from_the_allowed_lists():
    ok = LessonLabels(lesson_type="lesson", technique=["bending", "vibrato"], style="Chicago")
    assert ok.technique == ["bending", "vibrato"]

    with pytest.raises(ValidationError):
        LessonLabels(lesson_type="lesson", technique=["string bendz"])
    with pytest.raises(ValidationError):
        LessonLabels(lesson_type="lesson", style="Martian blues")


def test_labels_default_to_unknown_not_guessed():
    labels = LessonLabels(lesson_type="lesson")
    assert labels.key is None
    assert labels.style is None
    assert labels.technique == []
