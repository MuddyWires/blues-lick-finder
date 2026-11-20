"""Logfire tracing: every LLM call and tool call becomes a span.

Credentials come from `.logfire/logfire_credentials.json` (created by the
logfire CLI setup) or the LOGFIRE_TOKEN env var.
"""

import os

import logfire

SERVICE_NAME = "blues-lick-finder"

# Your own Logfire project page, e.g. https://logfire-eu.pydantic.dev/<org>/<project>/
# Set LOGFIRE_PROJECT_URL in .env to your own project page. Without it, trace
# links point at the Logfire home page (EU region) instead of a project.
TRACE_URL = (
    os.getenv("LOGFIRE_PROJECT_URL")  # blank (as in .env.example) falls back
    or "https://logfire-eu.pydantic.dev/"
).rstrip("/") + "/"


def setup_monitoring():
    # Send traces only when a Logfire token exists, so the app also runs without one.
    logfire.configure(service_name=SERVICE_NAME, send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()
    logfire.instrument_openai()  # embedding and level-labelling calls
