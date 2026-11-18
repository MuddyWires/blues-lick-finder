"""Simple Streamlit chat for the lick finder.

Run: uv run --group app streamlit run streamlit_app/app.py

Each question is one `chat turn` Logfire span tagged with the session id and
its cost. Session cost is kept per browser session; the all-sessions total is
read from your own Logfire project.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import dotenv
import logfire
import streamlit as st
from pydantic_ai.messages import ToolCallPart

dotenv.load_dotenv()

from lick_finder.agent import AgentResponse, LickFinderAgentConfig, create_agent  # noqa: E402
from lick_finder.monitoring import SERVICE_NAME, TRACE_URL, setup_monitoring  # noqa: E402
from lick_finder.tools import LickFinderTools  # noqa: E402
from lick_finder.turn import format_summary, turn_summary  # noqa: E402

st.set_page_config(page_title="Blues Lick Finder", page_icon="🎸")


@st.cache_resource
def get_setup():
    setup_monitoring()
    return LickFinderAgentConfig(), LickFinderTools()


@st.cache_data(ttl=60)
def all_sessions_cost():
    """Total cost across all sessions in your Logfire project (last 30 days)."""
    token = os.getenv("LOGFIRE_READ_TOKEN")
    if not token:
        return None
    from logfire.query_client import LogfireQueryClient

    base = "/".join(TRACE_URL.split("/")[:3])
    client = LogfireQueryClient(read_token=token, base_url=base)
    rows = client.query_json_rows(
        "select sum(cast(attributes->>'cost_usd' as double)) as cost from records "
        f"where service_name = '{SERVICE_NAME}' "
        "and span_name in ('chat session', 'chat turn')",
        min_timestamp=datetime.now(timezone.utc) - timedelta(days=30),
    )["rows"]
    return float(rows[0]["cost"] or 0.0)


config, tools = get_setup()
ss = st.session_state
ss.setdefault("session_id", uuid.uuid4().hex[:8])
ss.setdefault("messages", [])  # what is displayed
ss.setdefault("history", [])  # the model's message_history
ss.setdefault("totals", {"cost": 0.0, "input": 0, "output": 0})


def tool_calls(result):
    return [
        (p.tool_name, p.args)
        for m in result.new_messages()
        for p in m.parts
        if isinstance(p, ToolCallPart) and p.tool_name != "final_result"
    ]


def show_details(d):
    st.markdown(f"🔗 [Trace ↗]({d['trace_url']})")  # always visible
    with st.expander("Details", expanded=True):
        for name, args in d["tools"]:
            st.code(f"{name}({args})", language="python")
        st.caption(d["summary"])


with st.sidebar:
    st.caption(f"Model: {config.model}")
    t = ss.totals
    st.metric("This session", f"${t['cost']:.4f}")
    st.caption(f"{t['input']:,} in / {t['output']:,} out")
    total = all_sessions_cost()
    st.metric("All sessions (30 days)", "n/a" if total is None else f"${total:.4f}")
    if total is None:
        st.caption("Set LOGFIRE_READ_TOKEN to see this.")
    if st.button("New chat"):
        for k in ("session_id", "messages", "history", "totals"):
            ss.pop(k, None)
        st.rerun()
    st.link_button("Open Logfire project ↗", TRACE_URL)

st.title("🎸 Blues Lick Finder")
for m in ss.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if "details" in m:
            show_details(m["details"])

if question := st.chat_input("Ask about a blues lick or lesson…"):
    ss.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            # Rebuild the agent per question: asyncio.run uses a fresh event
            # loop each time, so a cached agent's HTTP client can break.
            agent = create_agent(config, tools)
            with logfire.span("chat turn", session_id=ss.session_id) as span:
                result = asyncio.run(
                    agent.run(question, message_history=ss.history, output_type=AgentResponse)
                )
                s = turn_summary(result, config.model)
                span.set_attribute("cost_usd", s["cost"] or 0.0)
                trace_id = format(span.get_span_context().trace_id, "032x")
        details = {
            "tools": tool_calls(result),
            "summary": format_summary(s),
            "trace_url": f"{TRACE_URL}?q=trace_id%3D%27{trace_id}%27",
        }
        st.write(result.output.answer)
        show_details(details)
    ss.history = result.all_messages()
    ss.messages.append({"role": "assistant", "content": result.output.answer, "details": details})
    ss.totals["cost"] += s["cost"] or 0.0
    ss.totals["input"] += s["input"]
    ss.totals["output"] += s["output"]
    st.rerun()
