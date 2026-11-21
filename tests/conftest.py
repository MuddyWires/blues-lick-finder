import os

import pytest
from dotenv import load_dotenv

from lick_finder.agent import LickFinderAgentConfig, LickFinderTools, create_agent
from lick_finder.business.lessons import LessonStore
from tests.llm.cost_tracker import display_total_usage

load_dotenv()

# The tests use the same model as the agent. Override with e.g.
# LICK_TEST_MODEL=openai:gpt-5.4-mini to compare against a bigger one.
TEST_MODEL = os.getenv("LICK_TEST_MODEL", LickFinderAgentConfig.model)

LESSONS = [
    {"video_id": "i6Ho6aubraw", "title": "Learn 10 Classic Blues Licks in the BB King Box!",
     "channel": "swiftlessons"},
    {"video_id": "sL1kT4VqYR8", "title": "5 Essential B.B. King Blues Licks | Lead Guitar Tutorial",
     "channel": "swiftlessons"},
]
LEVELS = {"i6Ho6aubraw": {"level": "intermediate"}, "sL1kT4VqYR8": {"level": "intermediate"}}


def pytest_addoption(parser):
    parser.addoption("--llm", action="store_true",
                     help="also run tests that call a real model (costs money)")


# Category markers are added from each test's folder, so `pytest -m business`
# and `pytest tests/unit/business` run the same tests.
CATEGORIES = {
    "business": "tests/unit/business: practice log, topic queue, lesson catalog",
    "agent": "tests/unit/agent: the thin tool layer, results and the search cap",
    "integrations": "tests/unit/integrations: search and YouTube data helpers",
    "reports": "tests/unit/reports: the usage report CLI",
    "models": "tests/unit/models: the pydantic data models (deep-links models are parked)",
    "helpers": "tests of the LLM test helpers (claims), no model calls",
    "architecture": "layer rules: business and integrations never import the agent",
}


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: calls a real model (costs money); run with --llm")
    for name, doc in CATEGORIES.items():
        config.addinivalue_line("markers", f"{name}: {doc}")


def pytest_collection_modifyitems(config, items):
    for item in items:
        parts = item.path.parts
        for name in ("business", "agent", "integrations", "reports", "models"):
            if "unit" in parts and name in parts:
                item.add_marker(getattr(pytest.mark, name))
        if item.path.name == "test_architecture.py":
            item.add_marker(pytest.mark.architecture)
        if item.path.name == "test_llm_helpers.py":
            item.add_marker(pytest.mark.helpers)

    if not config.getoption("--llm"):
        skip = pytest.mark.skip(reason="calls a real model; run with --llm")
    elif not os.getenv("OPENAI_API_KEY"):
        skip = pytest.mark.skip(reason="OPENAI_API_KEY is not set")
    else:
        return

    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    display_total_usage()


@pytest.fixture
def tools(tmp_path):
    """Tools over a temp practice log and topics file, with two known lessons
    and a fake search. Nothing touches the real data."""
    topics = tmp_path / "topics.txt"
    topics.write_text("")
    return LickFinderTools(
        practice_log_path=tmp_path / "practice_log.json",
        topics_path=topics,
        search_fn=lambda query, level=None: LESSONS,
        store=LessonStore(LESSONS, LEVELS),
    )


@pytest.fixture
def saved_tools(tools):
    """The same tools with both lessons saved and the first one liked."""
    tools.save_lesson("i6Ho6aubraw", "BB King box licks", "licks and phrasing", "", "intermediate")
    tools.save_lesson("sL1kT4VqYR8", "BB King essentials", "licks and phrasing", "", "intermediate")
    tools.like_lesson("i6Ho6aubraw")
    return tools


@pytest.fixture
def agent_for():
    def build(tools):
        return create_agent(LickFinderAgentConfig(model=TEST_MODEL), tools)

    return build
