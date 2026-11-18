"""The practice log: saved lessons and what the student did with them.

Business operations only. They return data or raise the errors below. Nothing
here knows an LLM exists: no prompts, no reply text.
"""

import json
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Optional

from .lessons import get_store
from ..paths import PRACTICE_LOG_PATH


class LessonNotInCatalog(Exception):
    """The video_id is not in the lesson data."""


class LessonAlreadySaved(Exception):
    """The lesson is already in the practice log."""


class LessonNotSaved(Exception):
    """The lesson is not in the practice log."""


class PracticeLog:
    def __init__(self, path: Path = PRACTICE_LOG_PATH, catalog=None):
        self.path = path
        self._catalog = catalog  # anything supporting `video_id in catalog`
        self._lock = Lock()

    def _read(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return []

    def _write(self, entries):
        self.path.write_text(json.dumps(entries, indent=2))

    def has(self, video_id: str) -> bool:
        return any(e["video_id"] == video_id for e in self._read())

    def add(self, video_id: str, song: str, technique: str, key: str, level: str) -> dict:
        if video_id not in (self._catalog or get_store()):
            raise LessonNotInCatalog

        with self._lock:
            entries = self._read()
            if any(e["video_id"] == video_id for e in entries):
                raise LessonAlreadySaved

            entry = {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "song": song,
                "technique": technique,
                "key": key,
                "level": level,
                "saved_date": date.today().isoformat(),
                "liked": False,
                "view_count": 0,
                "last_viewed": None,
            }
            entries.append(entry)
            self._write(entries)
            return entry

    def list(self, filter: Optional[str] = None, liked_only: bool = False, limit: int = 10):
        """Saved lessons, newest first."""
        entries = self._read()

        if liked_only:
            entries = [e for e in entries if e["liked"]]

        if filter:
            needle = filter.lower()
            entries = [
                e for e in entries
                if needle in " ".join(str(e.get(f, "")) for f in ("song", "technique", "key")).lower()
            ]

        entries.sort(key=lambda e: e["saved_date"], reverse=True)
        return entries[:limit]

    def record_view(self, video_id: str) -> dict:
        with self._lock:
            entries = self._read()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["view_count"] += 1
                    entry["last_viewed"] = date.today().isoformat()
                    self._write(entries)
                    return entry
            raise LessonNotSaved

    def like(self, video_id: str) -> dict:
        with self._lock:
            entries = self._read()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["liked"] = True
                    self._write(entries)
                    return entry
            raise LessonNotSaved
