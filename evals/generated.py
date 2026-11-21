import json
import random
import sys

from dotenv import load_dotenv
from openai import OpenAI

from lick_finder.integrations.embeddings import best_chunk_per_video, retrieve
from lick_finder.integrations.search import get_engine
from lick_finder.paths import DATA_DIR

load_dotenv()

QUESTION_MODEL = "gpt-5.4-nano"
QUESTIONS_PATH = DATA_DIR / "eval_questions.json"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200

PROMPT = """Write ONE question a guitar student might type into a search box that
this lesson excerpt answers. Paraphrase: never reuse a phrase of 4+ words from
the excerpt, and don't mention the title or channel. Reply with only the question."""

client = OpenAI()
engine = get_engine()
chunks, index, vector_index = engine.chunks, engine.index, engine.vector_index

random.seed(42)
sample = random.sample([c for c in chunks if len(c["content"]) > 1500], N)

questions = json.loads(QUESTIONS_PATH.read_text()) if QUESTIONS_PATH.exists() else {}
tokens = {"input": 0, "output": 0}
for c in sample:
    cid = f"{c['video_id']}:{c['start']}"
    if cid in questions:
        continue
    resp = client.chat.completions.create(
        model=QUESTION_MODEL,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Title: {c['title']}\n\n{c['content']}"},
        ],
    )
    tokens["input"] += resp.usage.prompt_tokens
    tokens["output"] += resp.usage.completion_tokens
    questions[cid] = resp.choices[0].message.content.strip()
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2))

if tokens["input"]:
    print(f"Question generation tokens: {tokens['input']} in, {tokens['output']} out")

print(f"\n{'method':12} hit@5  MRR   ({N} generated questions)")
for method in ("tfidf", "vector", "hybrid", "hybrid@0.5", "hybrid@0.25"):
    hits = mrr = 0
    for c in sample:
        question = questions[f"{c['video_id']}:{c['start']}"]
        results = best_chunk_per_video(retrieve(index, vector_index, question, method))
        ids = [r["video_id"] for r in results]
        if c["video_id"] in ids:
            hits += 1
            mrr += 1 / (ids.index(c["video_id"]) + 1)
    print(f"{method:12} {hits / N:.2f}   {mrr / N:.2f}")
