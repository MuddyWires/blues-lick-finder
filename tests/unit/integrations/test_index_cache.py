"""The app only reads the embedding cache; building it is the offline step."""

import numpy as np
import pytest

from lick_finder.integrations import embeddings
from lick_finder.integrations.embeddings import IndexNotBuilt, chunk_vectors


def chunks(n):
    return [{"title": f"t{i}", "content": f"c{i}"} for i in range(n)]


@pytest.fixture
def fake_embed(monkeypatch):
    calls = []

    def embed(texts):
        calls.append(len(texts))
        return np.eye(len(texts), 4, dtype=np.float32)

    monkeypatch.setattr(embeddings, "embed_texts", embed)
    return calls


def test_missing_embeddings_raise_instead_of_calling_the_api(tmp_path, fake_embed):
    with pytest.raises(IndexNotBuilt):
        chunk_vectors(chunks(3), tmp_path / "e.npz")

    assert fake_embed == []  # nothing was sent to OpenAI


def test_building_embeds_once_and_a_later_read_needs_no_calls(tmp_path, fake_embed):
    path = tmp_path / "e.npz"

    chunk_vectors(chunks(3), path, embed_missing=True)
    assert fake_embed == [3]

    chunk_vectors(chunks(3), path)  # a read, as the app does it
    chunk_vectors(chunks(3), path, embed_missing=True)
    assert fake_embed == [3]


def test_only_new_chunks_are_embedded_when_the_data_grows(tmp_path, fake_embed):
    path = tmp_path / "e.npz"
    chunk_vectors(chunks(3), path, embed_missing=True)

    chunk_vectors(chunks(5), path, embed_missing=True)

    assert fake_embed == [3, 2]
