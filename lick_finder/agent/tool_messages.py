"""Everything the agent reads back from a tool, keyed by result status.

Constants only: never put user input, model arguments, titles, comments or
transcripts into these strings. Business code returns data or raises; the tool
layer maps each outcome to a status, and ToolResult.of() attaches the message.
"""

MESSAGES = {
    "ok": "Done.",
    "already_saved": "That lesson is already saved. Tell the user and stop.",
    "not_in_catalog": (
        "That video is not in the lesson data. Tell the user, and use only "
        "a video_id from the search results."
    ),
    "not_saved": (
        "No saved lesson matches. Nothing was changed. Do not call this tool "
        "again; ask the user which saved lesson they mean."
    ),
    "queued": "Topic queued for the next data fetch. Tell the user to check back after it.",
    "already_queued": "That topic is already queued. Tell the user.",
    "invalid_topic": (
        "That topic could not be queued. Tell the user in one sentence and "
        "do not retry with another topic."
    ),
    "unsupported": (
        "That change is not supported. Nothing was changed. Tell the user in "
        "one sentence and call no more tools."
    ),
}
