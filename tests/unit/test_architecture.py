"""Layer rules: agent -> business -> integrations, never the other way.

business/ and integrations/ must know nothing about the agent, its prompts or
its tools, so they can be reused (an API, MCP, another agent) and tested
without a model.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2] / "lick_finder"

# layer -> prefixes it must not import
FORBIDDEN = {
    "business": ["lick_finder.agent", "pydantic_ai"],
    "integrations": ["lick_finder.agent", "lick_finder.business", "pydantic_ai"],
}


def imported_modules(path, root=ROOT):
    """Absolute names of everything a file imports."""
    package = ["lick_finder", *path.relative_to(root).parent.parts]
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - (node.level - 1)] if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            names.append(module)
            names += [f"{module}.{a.name}" for a in node.names]
    return names


@pytest.mark.parametrize("layer", FORBIDDEN)
def test_layer_does_not_import_what_is_above_it(layer):
    offenders = []
    for path in (ROOT / layer).glob("*.py"):
        for name in imported_modules(path):
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN[layer]):
                offenders.append(f"{path.name} imports {name}")

    assert offenders == []


def test_the_checker_catches_a_violation(tmp_path):
    # A throwaway package in tmp_path, so the test never writes into lick_finder/.
    root = tmp_path / "lick_finder"
    (root / "business").mkdir(parents=True)
    bad = root / "business" / "bad.py"
    bad.write_text("from ..agent.tool_messages import SAVED_LESSON_NOT_FOUND\n")

    assert "lick_finder.agent.tool_messages" in imported_modules(bad, root)
