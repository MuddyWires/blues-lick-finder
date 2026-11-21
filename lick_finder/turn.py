"""Per-question summary (tools, tokens, cost), shared by the CLI and the app."""

from pydantic_ai.messages import ToolCallPart

from .cost import calculate_cost


def turn_summary(result, model):
    """Tools called, tokens and cost for one question."""
    tools = [
        p.tool_name
        for m in result.new_messages()
        for p in m.parts
        if isinstance(p, ToolCallPart) and p.tool_name != "final_result"
    ]
    u = result.usage
    return {
        "tools": tools,
        "input": u.input_tokens,
        "output": u.output_tokens,
        "cost": calculate_cost(model, u.input_tokens, u.output_tokens),
    }


def format_summary(s):
    cost = f"${s['cost']:.4f}" if s["cost"] is not None else "n/a"
    return (
        f"tools: {', '.join(s['tools']) or 'none'} | {s['input']} in / {s['output']} out | {cost}"
    )
