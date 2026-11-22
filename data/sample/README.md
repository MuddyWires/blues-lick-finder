# Sample data

A small demo dataset so the app runs without fetching 80+ topics from YouTube.

- 36 lessons (titles, channels, tags, view counts) covering the example questions in the main README.
- Only a short transcript excerpt of each lesson (the first 4,500 characters), a description cut to 300 characters, and **no** comments or chapters.
- `levels.json` and `chunk_embeddings.npz` are prepared, so nothing needs `make index`.

It is not the full dataset and will not give the same answers as the real data. Rebuild it from your own `data/` with `uv run python -m scripts.make_sample`.

Run it with `make demo` (terminal chat) or `make demo-app` (Streamlit). Both still need an `OPENAI_API_KEY`, because the question is embedded and the agent is a hosted model.
