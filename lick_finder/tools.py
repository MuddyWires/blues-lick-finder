import json
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Literal, Optional

from .paths import PRACTICE_LOG_PATH, TOPICS_PATH
from .search import search


class LickFinderTools:
    """
    Searches stored blues lessons and manages a personal practice history.
    """

    def __init__(
        self,
        practice_log_path: Path = PRACTICE_LOG_PATH,
        topics_path: Path = TOPICS_PATH,
        search_fn=search,
    ):
        self.practice_log_path = practice_log_path
        self.topics_path = topics_path
        self._search = search_fn
        self._lock = Lock()

    def _read_log(self):
        if self.practice_log_path.exists():
            return json.loads(self.practice_log_path.read_text())
        return []

    def _write_log(self, entries):
        self.practice_log_path.write_text(json.dumps(entries, indent=2))

    def search_lessons(self, query: str, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search the stored blues lesson videos. The first step for any "find
        me a lesson" request.

        Args:
            query: The song or technique to search for.
            level: Optional: "beginner", "intermediate" or "advanced". Omit
                unless the user asked for a level. Lessons whose level is
                unclear are still returned.
        """
        return self._search(query, level=level)

    def save_lesson(self, video_id: str, song: str, technique: str, key: str, level: str):
        """
        Save a lesson to the practice history. Call only when the user
        chooses a specific lesson (e.g. "I'll practice this one"), never
        automatically after a search. Rejects duplicates.

        Args:
            video_id: The video's video_id from search results.
            song: The song the lesson teaches, or "" if general.
            technique: The technique the lesson teaches, e.g. "string bending".
            key: The musical key, or "" if none is named.
            level: Your estimate of the lesson's level.
        """
        with self._lock:
            entries = self._read_log()
            if any(e["video_id"] == video_id for e in entries):
                return "already saved"

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
            self._write_log(entries)
            return entry

    def get_history(self, filter: Optional[str] = None, liked_only: bool = False, limit: int = 10):
        """
        List saved lessons, newest first. Use for questions about what's
        already saved, what to practice next, or to find a lesson to replay.

        Args:
            filter: Text to match against song, technique, or key. Omit to
                list everything.
            liked_only: Only return liked lessons.
            limit: Max entries to return.
        """
        entries = self._read_log()

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

    def open_lesson(self, video_id: str):
        """Replay a saved lesson and record the view.

        Args:
            video_id: The video_id of the saved lesson to replay.
        """
        with self._lock:
            entries = self._read_log()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["view_count"] += 1
                    entry["last_viewed"] = date.today().isoformat()
                    self._write_log(entries)
                    return {"url": entry["url"], "view_count": entry["view_count"]}
            return f"video {video_id} is not in the practice history"

    def like_lesson(self, video_id: str):
        """Mark a saved lesson as liked.

        Args:
            video_id: The video_id of the saved lesson to like.
        """
        with self._lock:
            entries = self._read_log()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["liked"] = True
                    self._write_log(entries)
                    return entry
            return f"video {video_id} is not in the practice history"

    def queue_topic(self, topic: str) -> str:
        """
        Queue a new search topic for the next data fetch, when
        search_lessons finds nothing relevant. Does not fetch immediately.

        Args:
            topic: The topic to queue, phrased like a YouTube search.
        """
        with self._lock:
            existing = [
                line.strip() for line in self.topics_path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if topic.strip().lower() in (line.lower() for line in existing):
                return "already queued"

            with self.topics_path.open("a") as f:
                f.write(f"{topic}\n")
            return "queued"

    def change_saved_lesson(self, video_id: str, action: Literal["delete", "edit", "unlike"]) -> str:
        """
        Delete a saved lesson, edit its details, or un-like it. NOT
        SUPPORTED YET: this changes nothing and only returns a message.
        Call it when the user asks for one of these, so you can tell them
        plainly that it isn't possible.

        Args:
            video_id: The video_id of the saved lesson, if known.
            action: "delete", "edit" or "unlike".
        """
        return (
            f"Not supported yet: I can't {action} saved lessons, and nothing "
            "was changed. I can still open a saved lesson or mark one as liked."
        )
