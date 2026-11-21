"""The queue of search topics for the next data fetch (data/topics.txt).

Business operations only: they return nothing or raise the errors below.
The file is read line by line by the fetcher, where a `channel:` prefix or a
`#` has special meaning, so a topic must be one plain search phrase.
"""

from pathlib import Path
from threading import Lock

from ..paths import TOPICS_PATH

MAX_TOPIC_LENGTH = 100


class InvalidTopic(Exception):
    """The topic is not a single plain search phrase."""


class TopicAlreadyQueued(Exception):
    """The topic is already in the queue."""


def _is_valid(topic: str) -> bool:
    return (
        0 < len(topic) <= MAX_TOPIC_LENGTH
        and topic.isprintable()  # no newlines or other control characters
        and not topic.startswith("#")
        and not topic.lower().startswith("channel:")
    )


class TopicQueue:
    def __init__(self, path: Path = TOPICS_PATH):
        self.path = path
        self._lock = Lock()

    def add(self, topic: str) -> None:
        topic = topic.strip()
        if not _is_valid(topic):
            raise InvalidTopic

        with self._lock:
            existing = [
                line.strip()
                for line in self.path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if topic.lower() in (line.lower() for line in existing):
                raise TopicAlreadyQueued

            with self.path.open("a") as f:
                f.write(f"{topic}\n")
