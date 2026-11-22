"""Build the small demo dataset in data/sample/ from your full data/.

    uv run python -m scripts.make_sample

The sample keeps titles, channels, tags and a short transcript excerpt of about
40 lessons, and drops comments and chapters. It exists so a reviewer can run the
app without fetching 80+ topics from YouTube. Levels are copied from the full
levels.json; the excerpt chunks are embedded here (one small OpenAI call).
"""

import json
import re
from pathlib import Path

from dotenv import load_dotenv

from lick_finder.integrations.embeddings import chunk_vectors
from lick_finder.integrations.levels import apply_levels
from lick_finder.integrations.search import make_chunks
from lick_finder.paths import DATA_PATH, LEVELS_PATH

load_dotenv()

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
TRANSCRIPT_CHARS = 4500
DESCRIPTION_CHARS = 300

# (title pattern, how many lessons): chosen to cover the example questions in the README.
GROUPS = [
    (r"hide ?away", 3), (r"pride and joy", 3), (r"b\.?b\.? ?king", 5), (r"thrill is gone", 2),
    (r"killing floor", 3), (r"sweet home chicago", 2), (r"bend", 3), (r"pentatonic", 3),
    (r"turnaround", 2), (r"t-?bone", 2), (r"slide", 2), (r"12 bar|twelve bar", 2),
    (r"shuffle", 2), (r"albert king", 1), (r"magic sam", 1), (r"hoochie coochie", 1),
    (r"muddy waters", 1),
]  # fmt: skip


def pick(documents):
    chosen = {}
    for pattern, count in GROUPS:
        matches = [d for d in documents if d["transcript"] and re.search(pattern, d["title"], re.I)]
        for doc in sorted(matches, key=lambda d: -(d.get("view_count") or 0))[:count]:
            chosen.setdefault(doc["video_id"], doc)
    return list(chosen.values())


def trim(doc):
    return {
        **doc,
        "description": (doc.get("description") or "")[:DESCRIPTION_CHARS],
        "transcript": doc["transcript"][:TRANSCRIPT_CHARS],
        "comments": [],
        "chapters": [],
    }


def main():
    documents = json.loads(DATA_PATH.read_text())
    sample = [trim(d) for d in pick(documents)]
    levels = json.loads(LEVELS_PATH.read_text())

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lessons.json").write_text(json.dumps(sample, indent=1))
    (OUT / "levels.json").write_text(
        json.dumps(
            {d["video_id"]: levels[d["video_id"]] for d in sample if d["video_id"] in levels},
            indent=1,
        )
    )
    chunks = make_chunks(apply_levels(sample, levels))
    npz = OUT / "chunk_embeddings.npz"
    npz.unlink(missing_ok=True)
    chunk_vectors(chunks, path=npz, embed_missing=True)
    print(f"{len(sample)} lessons, {len(chunks)} chunks -> {OUT}")


if __name__ == "__main__":
    main()
