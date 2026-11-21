from collections import defaultdict

from pydantic_ai import RunUsage

# USD per million tokens. The nano price is from the course's cost_tracker;
# the mini price is from third-party trackers (check OpenAI's pricing page).
MODEL_PRICES = {
    "openai:gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "openai:gpt-5.4-mini": {"input": 0.75, "output": 4.50},
}

usages = defaultdict(RunUsage)


def calculate_cost(model_name, input_tokens, output_tokens):
    prices = MODEL_PRICES.get(model_name.lower())
    if prices is None:
        return None
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices[
        "output"
    ]


def capture_usage(model, result):
    usages[model] += result.usage


def display_total_usage():
    if not usages:
        return  # no model was called, e.g. a plain `pytest` run

    print()
    total_cost = 0
    for model, usage in usages.items():
        cost = calculate_cost(model, usage.input_tokens, usage.output_tokens)
        if cost is None:
            print(f"{model}: {usage.input_tokens} in, {usage.output_tokens} out (no price known)")
        else:
            print(f"{model}: ${cost:.6f}")
            total_cost += cost

    print(f"Total cost: ${total_cost:.6f}")
