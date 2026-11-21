"""Lesson levels (beginner / intermediate / advanced / unclear).

Reading is free: `apply_levels` only merges the cached levels. Labelling calls
the model, so it lives in `label_missing`, which the offline index step runs
(`python -m lick_finder.integrations.index`). The app never labels.
"""

import json
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from ..paths import LEVELS_PATH
from .files import write_text_atomic

load_dotenv()

# gpt-5.4-mini matches the existing data/levels.json (83% agreement on a 100-lesson
# sample; gpt-5.4-nano agreed 71-72% and labelled far more lessons "unclear").
LEVEL_MODEL = "gpt-5.4-mini"
LEVELS = {"beginner", "intermediate", "advanced", "unclear"}
BATCH_SIZE = 10  # lessons per model call

# USD per million tokens for LEVEL_MODEL (OpenAI pricing page).
INPUT_PRICE_PER_M = 0.75
OUTPUT_PRICE_PER_M = 4.50

usage = {"input": 0, "output": 0, "reasoning": 0}

DEFINITIONS = """beginner: explains basics (what a bend or the pentatonic box is), plays very
  slowly, or says it's for people starting out.
intermediate: assumes the box and basic bends; focuses on phrasing, licks in
  context, following chord changes.
advanced: chord-tone soloing, fast or complex runs, little basics explanation.
unclear: not enough evidence. Do not guess."""

PROMPT = f"""Classify this blues guitar lesson's level.
{DEFINITIONS}
Reply as JSON: {{"level": "...", "reason": "<one short sentence>"}}"""

BATCH_PROMPT = f"""Classify the level of each blues guitar lesson below. Judge every lesson on
its own text only.
{DEFINITIONS}
Reply as JSON with one entry per lesson, using the video_id you were given:
{{"results": [{{"video_id": "...", "level": "...", "reason": "<one short sentence>"}}]}}"""


@lru_cache(maxsize=1)
def get_client():
    return OpenAI()  # built on first use, so importing this module needs no API key


def lesson_text(doc):
    comments = " | ".join(str(c) for c in (doc.get("comments") or [])[:5])
    return (
        f"Title: {doc['title']}\nTags: {doc['tags']}\n"
        f"Transcript start: {(doc.get('transcript') or '')[:1500]}\n"
        f"Comments: {comments}"
    )


def _ask(client, system, text):
    resp = (client or get_client()).chat.completions.create(
        model=LEVEL_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
    )
    u = resp.usage
    usage["input"] += u.prompt_tokens
    usage["output"] += u.completion_tokens
    details = getattr(u, "completion_tokens_details", None)
    usage["reasoning"] += getattr(details, "reasoning_tokens", 0) or 0
    return resp.choices[0].message.content


def label_level(doc, client=None):
    """One lesson, one call. The fallback when a batch answer is missing."""
    out = json.loads(_ask(client, PROMPT, lesson_text(doc)))
    if out.get("level") not in LEVELS:
        return {"level": "unclear", "reason": "unparseable model output"}
    return out


def label_batch(docs, client=None):
    """Several lessons in one call. Returns {video_id: {level, reason}} for the
    lessons the model answered correctly. Lessons it skipped, repeated, mislabelled
    or gave an invalid level are left out so the caller can retry them one by one."""
    text = "\n\n".join(f"--- video_id: {d['video_id']}\n{lesson_text(d)}" for d in docs)
    try:
        items = json.loads(_ask(client, BATCH_PROMPT, text))["results"]
    except (ValueError, KeyError, TypeError):
        return {}
    wanted = {d["video_id"] for d in docs}
    out = {}
    for item in items if isinstance(items, list) else []:
        vid = item.get("video_id") if isinstance(item, dict) else None
        if vid in wanted and vid not in out and item.get("level") in LEVELS:
            out[vid] = {"level": item["level"], "reason": str(item.get("reason", ""))}
    return out


def read_levels(path=LEVELS_PATH):
    """The cached levels, with no OpenAI calls."""
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else {}


def apply_levels(documents, levels=None):
    """Merge cached levels into the documents. No OpenAI calls: a lesson with no
    cached level is 'unclear'."""
    levels = read_levels() if levels is None else levels
    for doc in documents:
        doc["level"] = levels.get(doc["video_id"], {}).get("level", "unclear")
    return documents


def label_missing(documents, path=LEVELS_PATH, batch_size=BATCH_SIZE, limit=None, client=None):
    """Label lessons missing from the levels file, `batch_size` per call. Saves
    after every batch (atomically), so an interrupted run resumes. Returns how
    many lessons were labelled."""
    path = Path(path)
    levels = read_levels(path)
    todo = [d for d in documents if d["video_id"] not in levels][:limit]
    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        got = label_batch(batch, client)
        for doc in batch:
            levels[doc["video_id"]] = got.get(doc["video_id"]) or label_level(doc, client)
        write_text_atomic(path, json.dumps(levels, indent=2))
        print(f"labelled {start + len(batch)}/{len(todo)} lessons")
    return len(todo)


def print_usage(labelled, total):
    cost = usage["input"] / 1e6 * INPUT_PRICE_PER_M + usage["output"] / 1e6 * OUTPUT_PRICE_PER_M
    print(
        f"\nTokens: {usage['input']} in, {usage['output']} out "
        f"({usage['reasoning']} of the output was reasoning)"
    )
    print(f"Cost for {labelled} videos: ${cost:.4f}")
    if labelled:
        print(f"Extrapolated to {total} videos: ${cost / labelled * total:.2f}")


if __name__ == "__main__":  # dry run: python -m lick_finder.integrations.levels 5
    from .youtube_data import read_cache

    documents = read_cache()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    labelled = label_missing(documents, limit=limit)
    print_usage(labelled, len(documents))
