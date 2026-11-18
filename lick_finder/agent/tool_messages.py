"""Everything the agent reads back from a tool.

Constants only: never put user input, model arguments, titles, comments or
transcripts into these strings. Business code returns data or raises; the
tool layer maps each outcome to one of these.
"""

SAVED_LESSON_NOT_FOUND = (
    "No saved lesson matches. Nothing was changed. Do not call this tool "
    "again; ask the user which saved lesson they mean."
)

CHANGE_UNSUPPORTED = {
    "delete": "Deleting saved lessons is not supported. Nothing was changed. "
              "Tell the user in one sentence and call no more tools.",
    "edit": "Editing saved lessons is not supported. Nothing was changed. "
            "Tell the user in one sentence and call no more tools.",
    "unlike": "Un-liking saved lessons is not supported. Nothing was changed. "
              "Tell the user in one sentence and call no more tools.",
}
