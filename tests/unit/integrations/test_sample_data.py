"""The bundled demo data in data/sample/ must work with no API key and no index step."""

import json
import subprocess
import sys
from pathlib import Path

from lick_finder.integrations.embeddings import chunk_vectors
from lick_finder.integrations.levels import apply_levels
from lick_finder.integrations.search import make_chunks

SAMPLE = Path(__file__).parents[3] / "data" / "sample"


def lessons():
    return json.loads((SAMPLE / "lessons.json").read_text())


def test_the_sample_is_small_and_has_no_comments_or_chapters():
    docs = lessons()

    assert 20 <= len(docs) <= 60
    assert all(d["comments"] == [] and d["chapters"] == [] for d in docs)
    assert all(len(d["transcript"]) <= 4500 and len(d["description"]) <= 300 for d in docs)


def test_every_sample_lesson_has_a_level():
    levels = json.loads((SAMPLE / "levels.json").read_text())

    assert {d["video_id"] for d in lessons()} <= set(levels)


def test_the_sample_engine_builds_from_the_cache_with_no_api_call():
    docs = apply_levels(lessons(), json.loads((SAMPLE / "levels.json").read_text()))
    chunks = make_chunks(docs)

    vectors = chunk_vectors(
        chunks, SAMPLE / "chunk_embeddings.npz"
    )  # raises IndexNotBuilt if any is missing

    assert len(vectors) == len(chunks) > 0


def test_lick_data_dir_points_the_app_at_another_folder(tmp_path):
    code = (
        "from lick_finder.paths import DATA_DIR, LEVELS_PATH; print(DATA_DIR); print(LEVELS_PATH)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={"LICK_DATA_DIR": str(tmp_path), "PATH": "", "PYTHONPATH": str(Path(__file__).parents[3])},
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip

    assert out == [str(tmp_path.resolve()), str(tmp_path.resolve() / "levels.json")]
