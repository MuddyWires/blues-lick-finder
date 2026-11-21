"""Search over lesson chunks: a TF-IDF index plus a vector index.

The indexes are built lazily on first use, not at import time, and only from
what is already on disk: this module never calls OpenAI to label lessons or
embed chunks and never fetches from YouTube. Those are offline steps:
`python -m lick_finder.integrations.youtube_data` (fetch), then
`python -m lick_finder.integrations.index` (label and embed). If embeddings are
missing, building the engine raises IndexNotBuilt.
"""

from dataclasses import dataclass
from functools import lru_cache

from gitsource import chunk_documents
from minsearch import Index

from .embeddings import IndexNotBuilt, VectorIndex, best_chunk_per_video, retrieve
from .levels import apply_levels
from .youtube_data import read_cache


@dataclass
class Engine:
    documents: list
    chunks: list
    index: Index
    vector_index: VectorIndex


def make_chunks(documents):
    """Transcripts are long, so split them into overlapping chunks and index
    the chunks. Each chunk keeps its video's metadata. Videos without a
    transcript are skipped."""
    transcript_docs = [doc for doc in documents if doc["transcript"]]
    return chunk_documents(transcript_docs, size=3000, step=1500, content_field_name="transcript")


@lru_cache(maxsize=1)
def get_engine():
    documents = apply_levels(read_cache())
    chunks = make_chunks(documents)

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
