# Sample data

A small demo dataset so the app runs without fetching 80+ topics from YouTube.

- 36 lessons (titles, channels, tags, view counts, links) covering the example questions in the main README.
- For each lesson, a short summary of what it teaches (the song or technique, the key, the level, the approach), written by a model in its own words for this demo. The summary is stored in the `transcript` field, because that is the field search reads. No transcripts, descriptions or comments are included, and a script checks that no summary copies a run of 7 words from its source.
- The videos and their content belong to their creators. Every lesson links to the original.
- `levels.json` and `chunk_embeddings.npz` are prepared, so nothing needs `make index`.

It is not the full dataset: search runs over summaries, so answers are less detailed than with the real data. Rebuild it from your own `data/` with `uv run python -m scripts.make_sample`.

Run it with `make demo` (terminal chat) or `make demo-app` (Streamlit). Both still need an `OPENAI_API_KEY`, because the question is embedded and the agent is a hosted model.
