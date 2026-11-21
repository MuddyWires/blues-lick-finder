"""Level labelling: batched, resumable, atomic, and never run by the app."""

import json
from types import SimpleNamespace

from lick_finder.integrations.files import write_text_atomic
from lick_finder.integrations.levels import apply_levels, label_batch, label_missing, read_levels


def doc(video_id):
    return {"video_id": video_id, "title": f"title {video_id}", "tags": [], "transcript": "x", "comments": []}


class FakeClient:
    """Stands in for the OpenAI client. `answer(user_text, system_prompt)` returns
    the JSON string the model would reply with; every call is recorded."""

    def __init__(self, answer):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._answer = answer

    def _create(self, model, response_format, messages):
        system, user = messages[0]["content"], messages[1]["content"]
        self.calls.append(user)
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, completion_tokens_details=None)
        content = self._answer(user, system)
        return SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def batch_answer(level="beginner", skip=()):
    """Answers a batch prompt for every video_id in it, except those in `skip`."""
    def answer(user, system):
        ids = [line.split("video_id: ")[1] for line in user.splitlines() if line.startswith("--- video_id: ")]
        if "results" not in system:  # a single-lesson prompt
            return json.dumps({"level": level, "reason": "single"})
        return json.dumps({"results": [{"video_id": i, "level": level, "reason": "batch"}
                                       for i in ids if i not in skip]})
    return answer


def test_apply_levels_merges_cached_levels_and_defaults_to_unclear():
    docs = apply_levels([doc("a"), doc("b")], {"a": {"level": "advanced"}})
    assert [d["level"] for d in docs] == ["advanced", "unclear"]


def test_label_batch_returns_only_valid_answers_for_the_lessons_asked():
    def answer(user, system):
        return json.dumps({"results": [
            {"video_id": "a", "level": "beginner", "reason": "ok"},
            {"video_id": "b", "level": "expert", "reason": "not a level"},
            {"video_id": "zzz", "level": "advanced", "reason": "not asked about"},
            {"video_id": "a", "level": "advanced", "reason": "duplicate"},
            "junk",
        ]})

    got = label_batch([doc("a"), doc("b"), doc("c")], FakeClient(answer))

    assert got == {"a": {"level": "beginner", "reason": "ok"}}


def test_label_batch_survives_unparseable_output():
    assert label_batch([doc("a")], FakeClient(lambda u, s: "not json")) == {}
    assert label_batch([doc("a")], FakeClient(lambda u, s: json.dumps({"other": 1}))) == {}


def test_label_missing_makes_one_call_per_batch_not_per_lesson(tmp_path):
    client = FakeClient(batch_answer())
    path = tmp_path / "levels.json"

    n = label_missing([doc(f"v{i}") for i in range(25)], path, batch_size=10, client=client)

    assert n == 25
    assert len(client.calls) == 3  # 10 + 10 + 5
    assert len(read_levels(path)) == 25


def test_a_lesson_the_batch_skipped_gets_one_single_call(tmp_path):
    client = FakeClient(batch_answer(skip={"v1"}))

    label_missing([doc("v0"), doc("v1"), doc("v2")], tmp_path / "levels.json", batch_size=10, client=client)

    assert len(client.calls) == 2  # one batch, one fallback for v1
    assert read_levels(tmp_path / "levels.json")["v1"]["reason"] == "single"


def test_already_labelled_lessons_cost_no_calls(tmp_path):
    path = tmp_path / "levels.json"
    path.write_text(json.dumps({"v0": {"level": "advanced", "reason": "cached"}}))
    client = FakeClient(batch_answer())

    label_missing([doc("v0"), doc("v1")], path, batch_size=10, client=client)

    assert len(client.calls) == 1
    assert read_levels(path)["v0"]["reason"] == "cached"  # untouched
    assert label_missing([doc("v0"), doc("v1")], path, client=client) == 0
    assert len(client.calls) == 1  # a second run is free


def test_limit_caps_how_many_lessons_are_labelled(tmp_path):
    client = FakeClient(batch_answer())
    assert label_missing([doc(f"v{i}") for i in range(30)], tmp_path / "l.json", limit=12, client=client) == 12


def test_write_text_atomic_replaces_the_file_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "levels.json"
    path.write_text("old")

    write_text_atomic(path, "new")

    assert path.read_text() == "new"
    assert [p.name for p in tmp_path.iterdir()] == ["levels.json"]


def test_a_failed_atomic_write_keeps_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / "levels.json"
    path.write_text("old")
    monkeypatch.setattr("lick_finder.integrations.files.os.replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))

    try:
        write_text_atomic(path, "new")
    except OSError:
        pass

    assert path.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["levels.json"]
