"""Per-session cost tracking, the same pattern as the course's cost_tracker."""

from collections import defaultdict

from pydantic_ai import RunUsage

# USD per million tokens (from the course's cost_tracker).
MODEL_PRICES = {
    "openai:gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "openai:gpt-5.4-mini": {"input": 0.75, "output": 4.50},
}

usages = defaultdict(RunUsage)


def calculate_cost(model_name, input_tokens, output_tokens):
    prices = MODEL_PRICES.get(model_name.lower())
    if prices is None:
        return None
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def capture_usage(model, result):
    usages[model] += result.usage


def total_cost():
    costs = [calculate_cost(m, u.input_tokens, u.output_tokens) for m, u in usages.items()]
    return sum(c for c in costs if c is not None)


def display_total_usage():
    if not usages:
        return

    print()
    for model, usage in usages.items():
        cost = calculate_cost(model, usage.input_tokens, usage.output_tokens)
        if cost is None:
            print(f"{model}: {usage.input_tokens} in, {usage.output_tokens} out (no price known)")
        else:
            print(f"{model}: ${cost:.6f} ({usage.input_tokens} in, {usage.output_tokens} out)")
    print(f"Session cost: ${total_cost():.6f}")
