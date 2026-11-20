"""Evaluate search on its own, without the agent.

    uv run python -m evals.retrieval             # dev questions only (use this while tuning)
    uv run python -m evals.retrieval --test      # also the held-out test questions (final comparison)
    uv run python -m evals.retrieval --k 3

Each case in evals/retrieval_cases.csv is a question plus the lessons that are
acceptable answers: every lesson with a transcript (so it can be retrieved)
whose title contains one of the `title_any` phrases. Cases from the same
`group` (a song or technique) stay in the same split, so near-duplicates never
land on both the dev and the test side. Search is scored the way the agent
uses it: the best chunk per video, top k videos.

Per method: hit rate, MRR, average retrieval latency (the vector methods include
one embedding call) and the average amount of text the model would receive.
The dev misses are printed so you can read them before changing the index.
"""

import argparse
import csv
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from lick_finder.integrations.embeddings import best_chunk_per_video, retrieve
from lick_finder.integrations.search import get_engine

load_dotenv()

CASES = Path(__file__).parent / "retrieval_cases.csv"
METHODS = ("tfidf", "vector", "hybrid", "hybrid@0.5", "hybrid@0.25")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def retrieval_metrics(cases, ranked_ids, k):
    hits, reciprocal_ranks = [], []
    for case, results in zip(cases, ranked_ids, strict=True):
        relevant = case["relevant_ids"]
        first_rank = next(
            (rank for rank, doc_id in enumerate(results[:k], 1) if doc_id in relevant),
            None,
        )
        hits.append(int(first_rank is not None))
        reciprocal_ranks.append(1 / first_rank if first_rank else 0)
    return {
        "hit_rate": sum(hits) / len(cases),
        "mrr": sum(reciprocal_ranks) / len(cases),
    }


def load_cases(documents):
    """Cases with their relevant video ids. Cases with none are dropped, with a warning."""
    indexed = [d for d in documents if d["transcript"]]
    cases = []
    for row in csv.DictReader(CASES.open(newline="")):
        phrases = [norm(p) for p in row["title_any"].split("|")]
        row["relevant_ids"] = {d["video_id"] for d in indexed if any(p in norm(d["title"]) for p in phrases)}
        if not row["relevant_ids"]:
            print(f"WARNING: no indexed lesson matches case {row['id']} ({row['title_any']}), skipped")
            continue
        cases.append(row)
    return cases


def run_method(engine, cases, method, k):
    ranked, latencies, sizes, chunks_by_case = [], [], [], []
    for case in cases:
        start = time.perf_counter()
        results = best_chunk_per_video(
            retrieve(engine.index, engine.vector_index, case["query"], method), limit=k
        )
        latencies.append(time.perf_counter() - start)
        ranked.append([r["video_id"] for r in results])
        sizes.append(sum(len(r["content"]) for r in results))
        chunks_by_case.append(results)
    return ranked, latencies, sizes, chunks_by_case


def report(name, cases, engine, k, show_misses):
    print(f"\n{name}: {len(cases)} questions, k={k}")
    print(f"{'method':12} hit@{k}  MRR    latency   text sent")
    misses = {}
    for method in METHODS:
        ranked, latencies, sizes, chunks = run_method(engine, cases, method, k)
        m = retrieval_metrics(cases, ranked, k)
        print(f"{method:12} {m['hit_rate']:.2f}   {m['mrr']:.2f}   "
              f"{1000 * sum(latencies) / len(cases):5.0f} ms  {sum(sizes) / len(cases):6.0f} chars")
        misses[method] = [(c, r, ch) for c, r, ch in zip(cases, ranked, chunks)
                          if not (set(r) & c["relevant_ids"])]
    if show_misses:
        titles = {d["video_id"]: d["title"] for d in engine.documents}
        method = "vector"  # the agent's default search method
        print(f"\nMisses for '{method}' ({len(misses[method])}):")
        for case, ranked_ids, _ in misses[method]:
            print(f"  #{case['id']} [{case['kind']}] {case['query']}")
            print(f"     wanted: {len(case['relevant_ids'])} lessons with '{case['title_any']}' in the title")
            print(f"     got:    {[titles.get(i, i)[:45] for i in ranked_ids[:k]]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--test", action="store_true", help="also score the held-out test split")
    args = ap.parse_args()

    engine = get_engine()
    cases = load_cases(engine.documents)
    dev = [c for c in cases if c["split"] == "dev"]
    test = [c for c in cases if c["split"] == "test"]
    assert not {c["group"] for c in dev} & {c["group"] for c in test}, "a group is on both sides"

    report("DEV", dev, engine, args.k, show_misses=True)
    if args.test:
        report("TEST", test, engine, args.k, show_misses=False)
    else:
        print(f"\n({len(test)} test questions held out; run with --test for the final comparison)")


if __name__ == "__main__":
    main()
