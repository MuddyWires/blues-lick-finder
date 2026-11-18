import pytest

from tests.llm.utils import claims


@pytest.mark.parametrize("answer", [
    "Saved xyz123 to your practice log.",
    "I've deleted that lesson from your history.",
    "Done. The lesson was removed.",
])
def test_claims_catches_an_answer_that_says_it_did_it(answer):
    assert claims(answer, "saved|deleted|removed")


@pytest.mark.parametrize("answer", [
    "I can't save xyz123 because it isn't in the lesson data.",
    "I can’t save xyz123 because it isn’t in the lesson database.",  # curly apostrophes
    "I can't delete saved lessons, so nothing was changed.",
    "Which one should I save?",
])
def test_claims_lets_a_refusal_or_a_question_through(answer):
    assert not claims(answer, "saved|deleted|removed")
