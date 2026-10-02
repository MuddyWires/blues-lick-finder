"""Fetch blues lesson videos from YouTube: metadata, transcripts, and top comments.

Results are cached to data/lessons.json. Run `uv run python notebooks/youtube_data.py`
to build or update the cache without opening Jupyter.
"""

import json
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

DATA_PATH = Path(__file__).parent.parent / "data" / "lessons.json"

TOPICS = [
    "BB King box blues lick lesson",
    "Freddie King Hideaway guitar lesson",
    "Stevie Ray Vaughan Pride and Joy guitar lesson",
    "blues turnaround licks lesson",
    "blues string bending technique lesson",
    "minor pentatonic blues licks beginner lesson",
    "Texas blues shuffle rhythm guitar lesson",
    "slow blues soloing lesson",
]
RESULTS_PER_TOPIC = 5
COMMENTS_PER_VIDEO = 20

transcript_api = YouTubeTranscriptApi()


def fetch_transcript(video_id):
    try:
        transcript = transcript_api.fetch(video_id, languages=["en"])
    except Exception:
        return None
    return " ".join(s.text for s in transcript.snippets)


def fetch_lessons(topics, results_per_topic):
    lessons = {}
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for topic in topics:
            print(f"Searching: {topic}")
            result = ydl.extract_info(f"ytsearch{results_per_topic}:{topic}", download=False)

            for entry in result["entries"]:
                video_id = entry["id"]
                if video_id in lessons:
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
    # Load cached lessons, fetching from YouTube on the first run and adding
    # comments to any lessons cached before comments were collected.
    path = Path(path)
    if path.exists():
        documents = json.loads(path.read_text())
    else:
        documents = fetch_lessons(TOPICS, RESULTS_PER_TOPIC)
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
