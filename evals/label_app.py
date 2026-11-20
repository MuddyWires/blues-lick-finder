"""Label each scenario's response as good or bad.

    uv run streamlit run evals/label_app.py

Reads a results CSV from evals/results/ (written by evals.run_scenarios) and
saves your labels next to it as <results file>_labels.csv. The results file is
never changed. Layout follows the course's manual labeling app
(documentation-agent/evals/manual/app.py).
"""

import csv
from datetime import datetime
from pathlib import Path

import streamlit as st

RESULTS_DIR = Path(__file__).parent / "results"
LABEL_FIELDS = ["id", "category", "question", "label", "failure_category", "comments", "labelled_at"]

# Failure types seen in the first runs; "other" plus the comment box covers the rest.
FAILURE_CATEGORIES = [
    "hallucination (invented lesson, quote, timestamp or detail)",
    "wrong tool call (called a tool it should not have)",
    "missing tool call (did not call a tool it needed)",
    "claimed an unsupported action was done",
    "ignored evidence in the tool results",
    "bad ranking or incomplete answer",
    "out of scope handled badly",
    "followed an injected instruction",
    "search loop or hit the search cap",
    "unnecessary clarifying question",
    "other (explain in comments)",
]


def labels_path(results_file):
    return results_file.with_name(results_file.stem + "_labels.csv")


def load_results(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def load_labels(path):
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def save_labels(path, labels):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels.values())


def find_next_unlabelled(rows, labels, start):
    """Next unlabelled row after `start`, wrapping around; None if all done."""
    n = len(rows)
    for offset in range(1, n + 1):
        i = (start + offset) % n
        if rows[i]["id"] not in labels:
            return i
    return None


def icon(labels, row):
    got = labels.get(row["id"])
    return "⬜" if not got else "✅" if got["label"] == "good" else "❌"


st.set_page_config(layout="wide", page_title="Lick Finder: label evals")

# ── File selection ──────────────────────────────────────────────────────────
st.sidebar.header("📂 Results file")
files = sorted(
    (f for f in RESULTS_DIR.rglob("results_*.csv") if not f.name.endswith("_labels.csv")),
    reverse=True,
)
if not files:
    st.error("No results CSV in evals/results/. Run `uv run python -m evals.run_scenarios` first.")
    st.stop()

results_file = st.sidebar.selectbox("Select results file", files, format_func=lambda f: str(f.relative_to(RESULTS_DIR)))
out_path = labels_path(results_file)

if st.session_state.get("loaded") != str(results_file):
    st.session_state.loaded = str(results_file)
    st.session_state.rows = load_results(results_file)
    st.session_state.labels = load_labels(out_path)
    st.session_state.current = next(
        (i for i, r in enumerate(st.session_state.rows) if r["id"] not in st.session_state.labels), 0
    )

rows, labels = st.session_state.rows, st.session_state.labels

# ── Navigation and progress ─────────────────────────────────────────────────
st.sidebar.header("🧭 Navigation")
selection = st.sidebar.selectbox(
    "Select scenario",
    range(len(rows)),
    index=st.session_state.current,
    format_func=lambda i: f"{icon(labels, rows[i])} #{rows[i]['id']} {rows[i]['question'][:32]}...",
)
if selection != st.session_state.current:
    st.session_state.current = selection
    st.rerun()

st.sidebar.progress(len(labels) / len(rows))
st.sidebar.text(f"Labeled: {len(labels)} / {len(rows)}")
good = sum(1 for v in labels.values() if v["label"] == "good")
st.sidebar.caption(f"Good: {good}   Bad: {len(labels) - good}")
st.sidebar.caption(f"Saving to {out_path.name}")

if len(labels) == len(rows):
    st.success("🎉 Everything is labeled!")

row = rows[st.session_state.current]
existing = labels.get(row["id"])

# ── Question and answer ─────────────────────────────────────────────────────
st.title(f"Scenario #{row['id']}  ({st.session_state.current + 1} / {len(rows)})")
st.caption(f"{row['category']} · {row['use_case']} · starting log: {row['seed']}")

st.subheader("❓ User question")
st.chat_message("user").write(row["question"])

st.subheader("📝 Agent answer")
with st.chat_message("assistant"):
    st.markdown(row["answer"] or "_No answer._")

col1, col2, col3 = st.columns(3)
col1.metric("Tools called", len(row["tools_called"].split(" > ")) if row["tools_called"] else 0)
col2.metric("Lessons added to log", row["saved_added"])
col3.metric("Cost", f"${float(row['cost_usd'] or 0):.4f}")
if row["topics_queued"]:
    st.warning(f"Topics queued: {row['topics_queued']}")
if row["error"]:
    st.error(row["error"])

st.subheader("🛠️ Tool calls")
with st.expander("View tool calls", expanded=False):
    st.text(row["tools_called"] or "none")
    for call in filter(None, row["tool_args"].split(" || ")):
        st.code(call, language="json")

st.subheader("🎯 What a good answer looks like")
st.info(row["expected_behavior"])

# Hidden by default so the automatic verdicts don't anchor your own label.
with st.expander("Automatic verdicts (open after you decide)"):
    st.markdown(f"**Tool check:** {row['auto_check']} {row['problems']}")
    st.markdown(f"**Judge:** {row.get('judge') or 'not run'}")
    st.caption(row.get("judge_reason", ""))

st.divider()

# ── Labeling ────────────────────────────────────────────────────────────────
st.subheader("⚖️ Your label")
if existing:
    st.caption(f"Currently labeled **{existing['label']}**. Click again to change it.")


def commit(label, failure_category, comments):
    labels[row["id"]] = {
        "id": row["id"], "category": row["category"], "question": row["question"],
        "label": label, "failure_category": failure_category, "comments": comments,
        "labelled_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_labels(out_path, labels)
    nxt = find_next_unlabelled(rows, labels, st.session_state.current)
    st.session_state.current = nxt if nxt is not None else min(st.session_state.current + 1, len(rows) - 1)
    st.rerun()


comments = st.text_area("Comments (optional)", value=existing["comments"] if existing else "",
                        height=80, key=f"comments_{row['id']}")

good_col, bad_col = st.columns(2)
with good_col:
    st.markdown("**Good**")
    if st.button("👍 Good", type="primary", use_container_width=True, key=f"good_{row['id']}"):
        commit("good", "", comments)

with bad_col:
    st.markdown("**Bad**")
    default = None
    if existing and existing["failure_category"] in FAILURE_CATEGORIES:
        default = FAILURE_CATEGORIES.index(existing["failure_category"])
    category = st.selectbox("Failure category (pick one, then click Bad)", FAILURE_CATEGORIES,
                            index=default, placeholder="Choose a failure category",
                            key=f"cat_{row['id']}")
    if st.button("👎 Bad", use_container_width=True, disabled=category is None, key=f"bad_{row['id']}"):
        commit("bad", category, comments)

# ── Reset ───────────────────────────────────────────────────────────────────
st.sidebar.divider()
if st.sidebar.checkbox("Allow reset") and st.sidebar.button("RESET ALL LABELS (caution)"):
    out_path.unlink(missing_ok=True)
    st.session_state.labels = {}
    st.session_state.current = 0
    st.rerun()
