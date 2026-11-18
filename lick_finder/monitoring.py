"""Logfire tracing: every LLM call and tool call becomes a span.

Credentials come from `.logfire/logfire_credentials.json` (created by the
logfire CLI setup) or the LOGFIRE_TOKEN env var.
"""

import os

import logfire

SERVICE_NAME = "blues-lick-finder"

# Your own Logfire project page, e.g. https://logfire-eu.pydantic.dev/<org>/<project>/
# Set LOGFIRE_PROJECT_URL in .env; the default is the author's project.
TRACE_URL = (
    os.getenv("LOGFIRE_PROJECT_URL")  # blank (as in .env.example) falls back
    or "https://logfire-eu.pydantic.dev/muddy-wires/starter-project/"
).rstrip("/") + "/"


def setup_monitoring():
    logfire.configure(service_name=SERVICE_NAME)
    logfire.instrument_pydantic_ai()
    logfire.instrument_openai()  # embedding and level-labelling calls
