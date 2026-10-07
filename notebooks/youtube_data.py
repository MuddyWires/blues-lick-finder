"""Fetch blues lesson videos from YouTube: metadata, transcripts, and top comments.

Searches are listed in data/topics.txt and results are cached to data/lessons.json.
Run `uv run python notebooks/youtube_data.py` to fetch any new topics without
opening Jupyter.
"""

import json
import os
import time
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from youtube_transcript_api import IpBlocked, RequestBlocked, YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig


class RotatingProxyConfig(GenericProxyConfig):
    # DataImpulse assigns a new exit IP per connection, so force the client to
    # open a fresh connection (and retry through a new IP) on every request.
    @property
    def prevent_keeping_connections_alive(self) -> bool:
        return True

    @property
    def retries_when_blocked(self) -> int:
        return 5


load_dotenv()

DATA_PATH = Path(__file__).parent.parent / "data" / "lessons.json"
TOPICS_PATH = Path(__file__).parent.parent / "data" / "topics.txt"

RESULTS_PER_TOPIC = 10
COMMENTS_PER_VIDEO = 20
TRANSCRIPT_DELAY_SEC = 6


def make_transcript_api():
    host = os.getenv("DATAIMPULSE_PROXY_HOST")
    port = os.getenv("DATAIMPULSE_PROXY_PORT")
    username = os.getenv("DATAIMPULSE_PROXY_USERNAME")
    password = os.getenv("DATAIMPULSE_PROXY_PASSWORD")
    if host and port and username and password:
        proxy_url = f"http://{username}:{password}@{host}:{port}"
        return YouTubeTranscriptApi(
            proxy_config=RotatingProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )
    return YouTubeTranscriptApi()


transcript_api = make_transcript_api()


def load_topics(path=TOPICS_PATH):
    lines = (line.strip() for line in Path(path).read_text().splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def fetch_transcript(video_id):
    # Let blocking errors through so a run stops instead of silently caching
    # empty transcripts; every other failure means the video has none.
    try:
        transcript = transcript_api.fetch(video_id, languages=["en"])
    except (RequestBlocked, IpBlocked):
        raise
    except Exception:
        return None
    return " ".join(s.text for s in transcript.snippets)


def fetch_lessons(topics, results_per_topic, skip_ids=()):
    lessons = {}
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for topic in topics:
            print(f"Searching: {topic}")
            result = ydl.extract_info(f"ytsearch{results_per_topic}:{topic}", download=False)

            for entry in result["entries"]:
                video_id = entry["id"]
                if video_id in lessons or video_id in skip_ids:
                    continue

                lessons[video_id] = {
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": entry.get("title"),
                    "channel": entry.get("channel"),
                    "description": (entry.get("description") or "")[:1000],
                    "tags": " ".join(entry.get("tags") or []),
                    "duration_sec": entry.get("duration"),
                    "view_count": entry.get("view_count"),
                    "topic": topic,
                    "transcript": fetch_transcript(video_id),
                }
                time.sleep(TRANSCRIPT_DELAY_SEC)

    return list(lessons.values())


def fetch_comments(video_ids):
    # Top comments by likes, skipping replies and the creator's own (usually promo) comments.
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": ["50", "50", "0", "0"], "comment_sort": ["top"]}},
    }

    comments_by_video = {}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for video_id in video_ids:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            comments = [
                {"text": c["text"], "likes": c.get("like_count") or 0}
                for c in info.get("comments") or []
                if c.get("parent") == "root" and not c.get("author_is_uploader")
            ]
            comments_by_video[video_id] = comments[:COMMENTS_PER_VIDEO]

    return comments_by_video


def load_lessons(path=DATA_PATH):
    # Load cached lessons, fetching any topics from topics.txt that aren't
    # cached yet and adding comments to lessons that don't have them.
    path = Path(path)
    documents = json.loads(path.read_text()) if path.exists() else []

    cached_topics = {doc["topic"] for doc in documents}
    new_topics = [topic for topic in load_topics() if topic not in cached_topics]
    for topic in new_topics:
        # Save after each topic so an interrupted run resumes where it stopped.
        cached_ids = {doc["video_id"] for doc in documents}
        documents += fetch_lessons([topic], RESULTS_PER_TOPIC, skip_ids=cached_ids)
        path.write_text(json.dumps(documents, indent=2))

    missing = [doc["video_id"] for doc in documents if "comments" not in doc]
    if missing:
        print(f"Fetching comments for {len(missing)} videos")
        comments_by_video = fetch_comments(missing)
        for doc in documents:
            if doc["video_id"] in comments_by_video:
                doc["comments"] = comments_by_video[doc["video_id"]]
        path.write_text(json.dumps(documents, indent=2))

    return documents


if __name__ == "__main__":
    documents = load_lessons()
    print(f"{len(documents)} lessons in {DATA_PATH}")
