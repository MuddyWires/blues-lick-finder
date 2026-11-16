import hashlib
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "chunk_embeddings.npz"
BATCH_SIZE = 100

client = OpenAI()


def chunk_text(chunk):
    return f"{chunk['title']}\n{chunk['content']}"


def text_key(text):
    return hashlib.sha256(text.encode()).hexdigest()


def embed_texts(texts):
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + BATCH_SIZE])
        vectors += [d.embedding for d in resp.data]
    return np.array(vectors, dtype=np.float32)


def chunk_vectors(chunks, path=CACHE_PATH):
    """One vector per chunk. Cached by hash of the chunk text, so rechunking
    only embeds chunks whose text is new."""
    cache = {}
    if Path(path).exists():
        saved = np.load(path)
        cache = dict(zip(saved["keys"].tolist(), saved["vectors"]))

    texts = [chunk_text(c) for c in chunks]
    keys = [text_key(t) for t in texts]
    missing = {k: t for k, t in zip(keys, texts) if k not in cache}
    if missing:
        print(f"Embedding {len(missing)} new chunks")
        new = embed_texts(list(missing.values()))
        cache.update(zip(missing.keys(), new))
        np.savez(path, keys=np.array(list(cache)), vectors=np.stack(list(cache.values())))

    return np.stack([cache[k] for k in keys])


class VectorIndex:
    def __init__(self, chunks):
        self.chunks = chunks
        self.vectors = chunk_vectors(chunks)  # unit length, so dot = cosine

    def search(self, query, num_results=50):
        scores = self.vectors @ embed_texts([query])[0]
        return [self.chunks[i] for i in np.argsort(-scores)[:num_results]]


def rrf(rankings, k=60, weights=None):
    """Reciprocal rank fusion of several ranked chunk lists, optionally weighted."""
    weights = weights or [1.0] * len(rankings)
    scores, by_id = {}, {}
    for ranking, weight in zip(rankings, weights):
        for rank, chunk in enumerate(ranking):
            cid = (chunk["video_id"], chunk["start"])
            by_id[cid] = chunk
            scores[cid] = scores.get(cid, 0) + weight / (k + rank + 1)
    return [by_id[cid] for cid in sorted(scores, key=scores.get, reverse=True)]


def retrieve(index, vector_index, query, method="hybrid", num_results=50):
    """method: "tfidf", "vector", "hybrid" (equal weights) or "hybrid@0.5"
    (TF-IDF weighted 0.5 against vector's 1.0)."""
    if method == "tfidf":
        return index.search(query, num_results=num_results)
    if method == "vector":
        return vector_index.search(query, num_results)
    tfidf_weight = float(method.split("@")[1]) if "@" in method else 1.0
    return rrf([index.search(query, num_results=num_results),
                vector_index.search(query, num_results)],
               weights=[tfidf_weight, 1.0])[:num_results]


def build_indexes(documents):
    """Chunks + TF-IDF index + vector index, for the eval scripts (no level field)."""
    from gitsource import chunk_documents
    from minsearch import Index

    chunks = chunk_documents([d for d in documents if d["transcript"]],
                             size=3000, step=1500, content_field_name="transcript")
    index = Index(text_fields=["title", "description", "tags", "content"],
                  keyword_fields=["video_id", "channel", "topic"])
    index.fit(chunks)
    return chunks, index, VectorIndex(chunks)


def best_chunk_per_video(results, limit=5):
    best = {}
    for chunk in results:
        best.setdefault(chunk["video_id"], chunk)
    return list(best.values())[:limit]
