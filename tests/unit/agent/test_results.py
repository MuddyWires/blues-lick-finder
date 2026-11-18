"""ToolResult statuses and their fixed messages."""

from lick_finder.agent.results import ToolResult


def test_every_status_has_a_fixed_message_without_placeholders():
    from typing import get_args

    from lick_finder.agent.results import Status
    from lick_finder.agent.tool_messages import MESSAGES

    assert set(MESSAGES) == set(get_args(Status))
    assert all("{" not in m for m in MESSAGES.values())
    assert ToolResult.of("queued").message == MESSAGES["queued"]
