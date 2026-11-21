"""Offline indexing: label new lessons and embed new chunks.

    uv run python -m lick_finder.integrations.index        # or: make index

Run it after fetching data. It is the only place that calls OpenAI to prepare
the data (batched level labelling, batched embeddings), and it skips anything
already cached, so a second run costs nothing. The app only reads the results.
"""

import sys

from .embeddings import VectorIndex
from .levels import BATCH_SIZE, apply_levels, label_missing, print_usage
from .search import make_chunks
from .youtube_data import read_cache


def build_index(batch_size=BATCH_SIZE):
    documents = read_cache()
    labelled = label_missing(documents, batch_size=batch_size)
    apply_levels(documents)
    chunks = make_chunks(documents)
    VectorIndex(chunks, embed_missing=True)
    return labelled, len(chunks)


if __name__ == "__main__":
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else BATCH_SIZE
    labelled, n_chunks = build_index(batch_size)
    if labelled:
        print_usage(labelled, labelled)
    print(
        f"Index ready: {labelled} lessons newly labelled, {n_chunks} chunks indexed (new ones embedded, the rest from cache)."
    )
