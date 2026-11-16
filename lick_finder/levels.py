import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .paths import LEVELS_PATH

load_dotenv()

LEVEL_MODEL = "gpt-5.4-mini"
LEVELS ={"beginner", "intermediate", "advanced", "unclear"}

# USD per million tokens (third-party trackers, March 2026; check OpenAI's page).
INPUT_PRICE_PER_M = 0.75
OUTPUT_PRICE_PER_M = 4.50

client = OpenAI()
usage = {"input": 0, "output": 0, "reasoning": 0}

PROMPT = """Classify this blues guitar lesson's level.
beginner: explains basics (what a bend or the pentatonic box is), plays very
  slowly, or says it's for people starting out.
intermediate: assumes the box and basic bends; focuses on phrasing, licks in
  context, following chord changes.
advanced: chord-tone soloing, fast or complex runs, little basics explanation.
unclear: not enough evidence. Do not guess.
Reply as JSON: {"level": "...", "reason": "<one short sentence>"}"""


def label_level(doc):
    comments = " | ".join(str(c) for c in (doc.get("comments") or [])[:5])
    text = (
        f"Title: {doc['title']}\nTags: {doc['tags']}\n"
        f"Transcript start: {(doc.get('transcript') or '')[:1500]}\n"
        f"Comments: {comments}"
    )
    resp = client.chat.completions.create(
        model=LEVEL_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text},
        ],
    )

    u = resp.usage
    usage["input"] += u.prompt_tokens
    usage["output"] += u.completion_tokens
    details = getattr(u, "completion_tokens_details", None)
    usage["reasoning"] += getattr(details, "reasoning_tokens", 0) or 0

    out = json.loads(resp.choices[0].message.content)
    if out.get("level") not in LEVELS:
        return {"level": "unclear", "reason": "unparseable model output"}
    return out


def read_levels(path=LEVELS_PATH):
    """The cached levels, with no OpenAI calls (unlike load_levels)."""
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else {}


def load_levels(documents, path=LEVELS_PATH, limit=None):
    """Label videos missing from levels.json (saved after each one, so an
    interrupted run resumes), then merge `level` into each document."""
    path = Path(path)
    levels = read_levels(path)
    todo =[d for d in documents if d["video_id"] not in levels][:limit]
    for i, doc in enumerate(todo, 1):
        levels[doc["video_id"]] = label_level(doc)
        path.write_text(json.dumps(levels, indent=2))
        entry = levels[doc["video_id"]]
        print(f"[{i}/{len(todo)}] {entry['level']:<12} {doc['title'][:55]} | {entry.get('reason', '')}")
    for doc in documents:
        doc["level"] = levels.get(doc["video_id"], {}).get("level", "unclear")
    return documents


def print_usage(labelled, total):
    cost = usage["input"] / 1e6 * INPUT_PRICE_PER_M + usage["output"] / 1e6 * OUTPUT_PRICE_PER_M
    print(f"\nTokens: {usage['input']} in, {usage['output']} out "
          f"({usage['reasoning']} of the output was reasoning)")
    print(f"Cost for {labelled} videos: ${cost:.4f}")
    if labelled:
        print(f"Extrapolated to {total} videos: ${cost / labelled * total:.2f}")


if __name__ == "__main__":  # dry run: python -m lick_finder.levels 5
    from .youtube_data import read_cache

    documents = read_cache()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    load_levels(documents, limit=limit)
    print_usage(limit or len(documents), len(documents))
