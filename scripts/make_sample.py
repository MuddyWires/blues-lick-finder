"""Build the small demo dataset in data/sample/ from your full data/.

    uv run python -m scripts.make_sample

The sample keeps each lesson's title, channel, tags, link and level, and replaces
the lesson's text with a short summary of what it teaches, written by a model in
its own words from the full transcript. No transcript, description or comment
text from the videos is kept, so the repo holds no one else's words. It exists so
a reviewer can run the app without fetching 80+ topics from YouTube.

The summary is stored in the `transcript` field, because that is the field search
chunks and embeds. Each summary is checked against its source: any run of 7 words
copied from the transcript makes the script retry once, then stop.
"""

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from lick_finder.integrations.embeddings import chunk_vectors
from lick_finder.integrations.levels import apply_levels, get_client
from lick_finder.integrations.search import make_chunks
from lick_finder.paths import DATA_PATH, LEVELS_PATH

load_dotenv()

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
SUMMARY_MODEL = "gpt-5.4-mini"
SOURCE_CHARS = 30000  # how much of the full transcript the summarizer reads
COPY_WORDS = 7  # a run of this many words shared with the source counts as copying

SUMMARY_PROMPT = """You write short, original summaries of blues guitar lessons for a search demo.
From the transcript, write 3 to 5 plain sentences in your own words: the song or technique
taught, the key if the speaker states one, who it suits (beginner, intermediate or advanced),
and how the lesson teaches it (for example a slow breakdown, tabs on screen, a backing track).
Never quote the speaker and do not reuse their phrases. No lists, no headings."""

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


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def copied_runs(summary, source, n=COPY_WORDS):
    """Runs of n words that appear in both the summary and the source."""
    w = words(summary)
    shingles = {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}
    src = words(source)
    return {
        " ".join(src[i : i + n])
        for i in range(len(src) - n + 1)
        if tuple(src[i : i + n]) in shingles
    }


def summarize(doc, avoid=()):
    prompt = SUMMARY_PROMPT
    if avoid:
        prompt += "\nDo not use these phrases, which were copied last time: " + "; ".join(
            sorted(avoid)
        )
    resp = get_client().chat.completions.create(
        model=SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Title: {doc['title']}\nChannel: {doc['channel']}\n\n{doc['transcript'][:SOURCE_CHARS]}",
            },
        ],
    )
    return resp.choices[0].message.content.strip()


def summary_for(doc):
    text = summarize(doc)
    copied = copied_runs(text, doc["transcript"])
    if copied:
        text = summarize(doc, avoid=copied)
        copied = copied_runs(text, doc["transcript"])
    if copied:
        sys.exit(f"{doc['video_id']}: summary still copies the transcript: {sorted(copied)[:3]}")
    return text


def shrink(doc):
    """The lesson with its own text replaced by a summary; no description, comments or chapters."""
    return {
        **doc,
        "description": "",
        "transcript": summary_for(doc),
        "comments": [],
        "chapters": [],
    }


def main():
    documents = json.loads(DATA_PATH.read_text())
    sample = [shrink(d) for d in pick(documents)]
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
