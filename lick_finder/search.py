"""Search over lesson chunks: a TF-IDF index plus a vector index.

The indexes are built lazily on first use, not at import time. Building them
labels any unlabelled lessons and embeds any new chunks (small OpenAI calls,
cached on disk), but never fetches from YouTube: that is
`python -m lick_finder.youtube_data`.
"""

from dataclasses import dataclass
from functools import lru_cache

from gitsource import chunk_documents
from minsearch import Index

from .embeddings import VectorIndex, best_chunk_per_video, retrieve
from .levels import load_levels
from .youtube_data import read_cache


@dataclass
class Engine:
    documents: list
    chunks: list
    index: Index
    vector_index: VectorIndex


@lru_cache(maxsize=1)
def get_engine():
    documents = load_levels(read_cache())

    # Transcripts are long, so split them into overlapping chunks and index
    # the chunks. Each chunk keeps its video's metadata. Videos without a
    # transcript are skipped.
    transcript_docs = [doc for doc in documents if doc["transcript"]]
    chunks = chunk_documents(
        transcript_docs, size=3000, step=1500, content_field_name="transcript"
    )

    index = Index(
        text_fields=["title", "description", "tags", "content"],
        keyword_fields=["video_id", "channel", "topic", "level"],
    )
    index.fit(chunks)

    return Engine(documents, chunks, index, VectorIndex(chunks))


def filter_level(results, level):
    """Keep results of the given level. Unclear lessons stay eligible: we
    can't rule them out. With no level, everything passes."""
    if not level:
        return results
    return [r for r in results if r["level"] in (level, "unclear")]


def search(query, level=None, method="vector"):
    engine = get_engine()
    results = retrieve(
        engine.index, engine.vector_index, query, method, 200 if level else 50
    )
    # Keep only the best chunk per video, so we return 5 different videos.
    return best_chunk_per_video(filter_level(results, level))
