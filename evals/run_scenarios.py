"""Run every scenario in evals/scenarios.csv against the real agent and save
the results to evals/results/results_<timestamp>.csv.

    uv run python -m evals.run_scenarios            # all scenarios
    uv run python -m evals.run_scenarios 1 15 50    # only these ids
    uv run python -m evals.run_scenarios --workers 2
    uv run python -m evals.run_scenarios --model openai:gpt-5.4-mini

Each scenario gets its own temp practice log and topics file, so the real data
is never touched. The `seed` column picks the starting log: `default` is a copy
of data/practice_log.json, `empty` is nothing saved, `many` is 12 saved lessons.
The `setup` column holds earlier user turns (separated by `||`) that run first,
so a scenario can start from a conversation. Only the last question is scored.

The automatic check is deliberately loose: every tool in `expected_tools` must
have been called and none in `forbidden_tools` (`*` means no tool at all). The
answers still need a human (or judge) read against `expected_behavior`.
"""

import argparse
import asyncio
import csv
import json
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.exceptions import UsageLimitExceeded

from lick_finder.agent import (
    USAGE_LIMITS,
    LickFinderAgentConfig,
    LickFinderTools,
    create_agent,
    present,
    render,
)
from lick_finder.integrations.youtube_data import read_cache
from lick_finder.paths import PRACTICE_LOG_PATH, TOPICS_PATH
from lick_finder.turn import is_output_tool, turn_summary
from tests.llm.cost_tracker import display_total_usage
from tests.llm.judge import judge
from tests.llm.utils import collect_tool_returns, collect_tools

load_dotenv()

HERE = Path(__file__).parent
SCENARIOS = HERE / "scenarios.csv"
RESULTS_DIR = HERE / "results"
MANY = 12


def split(value, sep="|"):
    return [v.strip() for v in value.split(sep) if v.strip()]


def make_tools(seed, tmp):
    log, topics = tmp / "practice_log.json", tmp / "topics.txt"
    topics.write_text(TOPICS_PATH.read_text() if TOPICS_PATH.exists() else "")
    if seed == "default" and PRACTICE_LOG_PATH.exists():
        shutil.copy(PRACTICE_LOG_PATH, log)
    tools = LickFinderTools(practice_log_path=log, topics_path=topics)
    if seed == "many":
        for lesson in read_cache()[:MANY]:
            video_id = lesson["video_id"]
            tools.save_lesson(video_id, "seeded song", "seeded technique", "", "unclear")
    return tools


def read_log(tools):
    return (
        json.loads(tools.practice_log_path.read_text()) if tools.practice_log_path.exists() else []
    )


def topic_lines(tools):
    return [line for line in tools.topics_path.read_text().splitlines() if line.strip()]


def tool_calls(result):
    """(name, args) for each tool the agent called in the last turn."""
    return [
        (p.tool_name, p.args)
        for m in result.new_messages()
        for p in m.parts
        if p.part_kind == "tool-call" and not is_output_tool(p.tool_name)
    ]


def check(called, expected, forbidden):
    names = set(called)
    problems = []
    missing = [t for t in expected if t not in names]
    if missing:
        problems.append("missing " + "+".join(missing))
    if forbidden == ["*"]:
        if names:
            problems.append("called tools: " + "+".join(sorted(names)))
    else:
        bad = [t for t in forbidden if t in names]
        if bad:
            problems.append("forbidden " + "+".join(bad))
    return problems


async def run_one(row, agent_cfg, sem, use_judge):
    async with sem:
        out = {
            k: row[k]
            for k in ("id", "category", "use_case", "seed", "question", "expected_behavior")
        }
        out.update(
            tools_called="",
            tool_args="",
            answer="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            seconds=0.0,
            judge="",
            judge_reason="",
            lessons_returned=0,
            lessons_dropped=0,
            saved_added=0,
            topics_queued="",
            auto_check="",
            problems="",
            error="",
        )
        tmp = Path(tempfile.mkdtemp(prefix=f"scenario{row['id']}_"))
        start = time.time()
        try:
            tools = make_tools(row["seed"], tmp)
            agent = create_agent(agent_cfg, tools)
            history = []
            for turn in split(row["setup"], "||"):
                r = await agent.run(
                    turn,
                    message_history=history,
                    usage_limits=USAGE_LIMITS,
                )
                history = r.all_messages()
            before_log, before_topics = read_log(tools), topic_lines(tools)

            result = await agent.run(
                row["question"],
                message_history=history,
                usage_limits=USAGE_LIMITS,
            )
            shown = present(result.output, tools.lesson_store())
            summary = turn_summary(result, agent_cfg.model)
            calls = tool_calls(result)
            problems = check(
                summary["tools"], split(row["expected_tools"]), split(row["forbidden_tools"])
            )

            after_log = read_log(tools)
            out.update(
                tools_called=" > ".join(summary["tools"]),
                tool_args=" || ".join(f"{n}({a})" for n, a in calls),
                answer=render(shown),
                lessons_returned=len(shown.lessons),
                lessons_dropped=len(shown.dropped),
                input_tokens=summary["input"],
                output_tokens=summary["output"],
                cost_usd=round(summary["cost"] or 0, 6),
                saved_added=len(after_log) - len(before_log),
                topics_queued="; ".join(topic_lines(tools)[len(before_topics) :]),
                auto_check="PASS" if not problems else "FAIL",
                problems="; ".join(problems),
            )
            if use_judge:
                messages = result.new_messages()
                fb = await judge(
                    [row["expected_behavior"]],
                    output=render(shown),
                    tool_calls=[str(t) for t in collect_tools(messages)],
                    tool_results=[str(t) for t in collect_tool_returns(messages)],
                )
                out["judge"] = "PASS" if all(c.passed for c in fb.criteria) else "FAIL"
                out["judge_reason"] = " | ".join(c.judgement for c in fb.criteria)
        except UsageLimitExceeded:
            out.update(
                auto_check="FAIL",
                problems="hit request limit (stuck loop)",
                error="UsageLimitExceeded",
            )
        except Exception as e:  # keep the batch going
            out.update(auto_check="ERROR", error=f"{type(e).__name__}: {e}")
        finally:
            out["seconds"] = round(time.time() - start, 1)
            shutil.rmtree(tmp, ignore_errors=True)
        print(
            f"#{row['id']:>3} {out['category']:<16} {out['auto_check']:<5} {out['tools_called'] or '-'}",
            flush=True,
        )
        return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="only run these scenario ids")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge on answers")
    ap.add_argument(
        "--model", help="agent model, e.g. openai:gpt-5.4-mini (default: the agent's own)"
    )
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    with SCENARIOS.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if args.ids:
        rows = [r for r in rows if r["id"] in args.ids]

    cfg = LickFinderAgentConfig(model=args.model) if args.model else LickFinderAgentConfig()
    sem = asyncio.Semaphore(args.workers)
    print(f"Running {len(rows)} scenarios with {cfg.model}\n")
    results = await asyncio.gather(*(run_one(r, cfg, sem, not args.no_judge) for r in rows))

    RESULTS_DIR.mkdir(exist_ok=True)
    tag = f"_{args.model.split(':')[-1]}" if args.model else ""
    path = RESULTS_DIR / f"results_{datetime.now():%Y%m%d_%H%M%S}{tag}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)

    by_cat = {}
    for r in results:
        c = by_cat.setdefault(r["category"], [0, 0, 0])
        c[2] += 1
        c[0] += r["auto_check"] == "PASS"
        c[1] += r["judge"] == "PASS"
    print(f"\n{'category':<16} tools  judge")
    for cat, (tools_ok, judge_ok, n) in by_cat.items():
        print(f"  {cat:<16} {tools_ok}/{n}   {judge_ok}/{n}")
    print(
        f"Agent cost: ${sum(r['cost_usd'] for r in results):.4f} (judge cost in the usage lines below)"
    )
    display_total_usage()
    print(f"Saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
