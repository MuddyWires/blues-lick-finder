"""Turn real questions from your Logfire traces into candidate eval scenarios.

    uv run python -m evals.logs_to_cases              # last 30 days
    uv run python -m evals.logs_to_cases --days 7

Reads the agent's `invoke_agent` spans (needs LOGFIRE_READ_TOKEN, the same token
the report CLI uses), keeps the questions that started a conversation, drops
duplicates, and writes evals/results/log_cases_<time>.csv in the same columns
as evals/scenarios.csv. The file is a starting point, not ground truth: what
the agent called is recorded in `logged_tools`, but `expected_behavior` is left
blank for you to fill in and review before you copy rows into scenarios.csv.
"""

import argparse
import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from reports.report_cli import get_client, load_menu

RESULTS_DIR = Path(__file__).parent / "results"
SCENARIOS = Path(__file__).parent / "scenarios.csv"
FIELDS = [
    "id",
    "category",
    "use_case",
    "seed",
    "setup",
    "question",
    "expected_behavior",
    "expected_tools",
    "forbidden_tools",
    "logged_tools",
    "trace_id",
]

# Static SQL, same rule as reports/menu.json: no user input goes into a query.
SQL = (
    "select trace_id, start_timestamp, attributes->'pydantic_ai.all_messages' as messages, "
    "cast(attributes->>'pydantic_ai.new_message_index' as bigint) as new_index "
    "from records where service_name = '$SERVICE' and span_name like 'invoke_agent%' "
    "order by start_timestamp"
)


def as_list(value):
    return json.loads(value) if isinstance(value, str) else value


def first_question(messages, new_index):
    """The user's question for this run, or None if it is a follow-up turn.

    Follow-ups need the earlier turns as context, which a single span does not
    give us cleanly, so only conversation starters are kept."""
    if new_index not in (0, None):
        return None
    for m in messages:
        if m.get("role") == "user":
            return " ".join(
                p.get("content", "") for p in m["parts"] if p.get("type") == "text"
            ).strip()
    return None


def tools_called(messages):
    return [
        p["name"]
        for m in messages
        if m.get("role") == "assistant"
        for p in m["parts"]
        if p.get("type") == "tool_call" and p.get("name") != "final_result"
    ]


def next_id():
    with SCENARIOS.open(newline="") as f:
        return max(int(r["id"]) for r in csv.DictReader(f)) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    menu = load_menu()
    since = datetime.now(UTC) - timedelta(days=args.days)
    rows = get_client().query_json_rows(
        SQL.replace("$SERVICE", menu["service"]), min_timestamp=since
    )["rows"]

    seen = {r["question"].strip().lower() for r in csv.DictReader(SCENARIOS.open(newline=""))}
    out, n = [], next_id()
    for row in rows:
        messages = as_list(row["messages"])
        question = first_question(messages, row["new_index"])
        if not question or question.lower() in seen:
            continue
        seen.add(question.lower())
        out.append(
            {
                "id": n,
                "category": "from_logs",
                "use_case": "logged",
                "seed": "default",
                "setup": "",
                "question": question,
                "expected_behavior": "",
                "expected_tools": "",
                "forbidden_tools": "",
                "logged_tools": "|".join(tools_called(messages)),
                "trace_id": row["trace_id"],
            }
        )
        n += 1

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"log_cases_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    print(
        f"{len(rows)} agent runs in the last {args.days} days -> {len(out)} new candidate questions"
    )
    print(
        f"Saved {path}\nFill in expected_behavior, review, then copy the rows you keep into evals/scenarios.csv."
    )


if __name__ == "__main__":
    main()
