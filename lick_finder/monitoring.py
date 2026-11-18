"""Logfire tracing: every LLM call and tool call becomes a span.

Credentials come from `.logfire/logfire_credentials.json` (created by the
logfire CLI setup) or the LOGFIRE_TOKEN env var.
"""

import logfire

TRACE_URL = "https://logfire-eu.pydantic.dev/muddy-wires/starter-project/"


def setup_monitoring():
    logfire.configure(service_name="blues-lick-finder")
    logfire.instrument_pydantic_ai()
    logfire.instrument_openai()  # embedding and level-labelling calls
