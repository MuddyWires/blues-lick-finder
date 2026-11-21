"""Run the LLM judge on every labeled scenario and compare it with your labels.

    uv run python -m evals.run_judge                      # all labeled results files
    uv run python -m evals.run_judge --results evals/results/results_X.csv
    uv run python -m evals.run_judge --model openai:gpt-5.4-nano

Reads each evals/results/**/results_*.csv that has a matching *_labels.csv
(written by the labeling app), joins them by scenario id, runs the judge, and
prints accuracy, precision and recall with "bad" as the positive class (as in
the course's evals/manual/run_judge.py), the confusion matrix, and every
disagreement. Details are saved next to each labels file as *_judged.csv.
"""

import argparse
import asyncio
import csv
from pathlib import Path

from dotenv import load_dotenv

from evals.judge import JUDGE_MODEL, create_judge_agent, format_judge_prompt, load_setups

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"
MIN_LABELS = 30  # below this, the numbers are too noisy to trust
MIN_BAD = 8


def labeled_files(only):
    if only:
        return [Path(p) for p in only]
    files = RESULTS_DIR.rglob("results_*.csv")
    return sorted(
        f
        for f in files
        if not f.name.endswith(("_labels.csv", "_judged.csv"))
        and f.with_name(f.stem + "_labels.csv").exists()
    )


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


async def judge_one(judge, sem, row, setup):
    async with sem:
        try:
            out = (await judge.run(format_judge_prompt(row, setup))).output
            return out.label, out.failure_category, out.reasoning
        except Exception as e:  # an error is not a verdict, so it is kept out of the metrics
            return "error", "", f"{type(e).__name__}: {e}"


def metrics(pairs):
    """pairs: (human, judge) labels. 'bad' is the positive class."""
    tp = sum(h == "bad" and j == "bad" for h, j in pairs)
    fp = sum(h == "good" and j == "bad" for h, j in pairs)
    fn = sum(h == "bad" and j == "good" for h, j in pairs)
    tn = sum(h == "good" and j == "good" for h, j in pairs)
    n = len(pairs)
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "accuracy": (tp + tn) / n if n else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def pct(x):
    return "n/a (undefined)" if x is None else f"{x:.3f} ({x * 100:.1f}%)"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="*", help="results CSV(s); default: every one with labels")
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    files = labeled_files(args.results)
    if not files:
        print(
            "No labeled results found. Label some scenarios in the app first:\n"
            "  uv run streamlit run evals/label_app.py"
        )
        return

    setups, judge, sem = (
        load_setups(),
        create_judge_agent(args.model),
        asyncio.Semaphore(args.workers),
    )
    rows = []
    for f in files:
        labels = {r["id"]: r for r in read(f.with_name(f.stem + "_labels.csv"))}
        results = [r for r in read(f) if r["id"] in labels]
        print(f"{f.name}: {len(results)} labeled scenarios")
        verdicts = await asyncio.gather(
            *(judge_one(judge, sem, r, setups.get(r["id"], "")) for r in results)
        )
        file_rows = []
        for r, (label, category, reasoning) in zip(results, verdicts):
            human = labels[r["id"]]
            file_rows.append(
                {
                    "file": f.name,
                    "id": r["id"],
                    "category": r["category"],
                    "question": r["question"],
                    "human_label": human["label"],
                    "human_failure": human["failure_category"],
                    "human_comment": human["comments"],
                    "judge_label": label,
                    "judge_failure": category,
                    "judge_reasoning": reasoning,
                    "agree": human["label"] == label,
                }
            )
        rows += file_rows
        if file_rows:
            out = f.with_name(f.stem + "_judged.csv")
            with out.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(file_rows[0]))
                w.writeheader()
                w.writerows(file_rows)
            print(f"  details saved to {out}")

    errors = [r for r in rows if r["judge_label"] == "error"]
    scored = [r for r in rows if r["judge_label"] != "error"]
    m = metrics([(r["human_label"], r["judge_label"]) for r in scored])

    print("\n" + "=" * 50 + f"\nJudge: {args.model}\n" + "=" * 50)
    print(f"Labeled samples scored: {m['n']}   judge errors skipped: {len(errors)}")
    print(
        f"Human labels: {sum(r['human_label'] == 'good' for r in scored)} good, "
        f"{sum(r['human_label'] == 'bad' for r in scored)} bad"
    )
    print(f"Accuracy:  {pct(m['accuracy'])}")
    print(f"Precision (class='bad'): {pct(m['precision'])}")
    print(f"Recall    (class='bad'): {pct(m['recall'])}")
    print("\nConfusion matrix:")
    print("                 Judge 'good'   Judge 'bad'")
    print(f"Human 'good'     {m['tn']:<14} {m['fp']}")
    print(f"Human 'bad'      {m['fn']:<14} {m['tp']}")

    n_bad = m["tp"] + m["fn"]
    if m["n"] < MIN_LABELS or n_bad < MIN_BAD:
        print(
            f"\nWARNING: only {m['n']} labels ({n_bad} bad). Under {MIN_LABELS} labels or {MIN_BAD} bad "
            "ones, these numbers are too noisy to guide prompt changes."
        )

    wrong = [r for r in scored if not r["agree"]]
    print(f"\n--- Disagreements ({len(wrong)}) ---")
    for r in wrong:
        print(f"#{r['id']} [{r['category']}] {r['question']}")
        print(
            f"  Human: {r['human_label']} {r['human_failure']} {('— ' + r['human_comment']) if r['human_comment'] else ''}"
        )
        print(f"  Judge: {r['judge_label']} ({r['judge_failure']}) {r['judge_reasoning'][:300]}")
        print("-" * 30)
    for r in errors:
        print(f"ERROR #{r['id']}: {r['judge_reasoning']}")


if __name__ == "__main__":
    asyncio.run(main())
