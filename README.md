# Blues Lick Finder & Tracker

An agent that finds well-taught blues guitar lessons for a song or technique, ranks them by teaching quality, and automatically builds a tagged practice log.

## The Problem

When I learn blues licks, I keep searching for the same lessons over and over. YouTube ranks videos by engagement, not by how well they teach, so the clearest lessons are often buried under the most popular ones.

## What It Does

You give the agent a song or a technique (for example "BB King box licks" or "Hideaway intro"). The agent:

1. Searches YouTube for candidate lesson videos using the YouTube Data API.
2. Pulls transcripts with `youtube-transcript-api` where they exist.
3. Scores each video against a teaching-quality rubric (for example clear breakdown, slow demonstration, tab or notation, explains the why behind the lick) and returns a ranked list with a short justification for each video.
4. Adds the lessons you pick to a practice log, tagged by song, technique, and key, so you don't have to search for the same lick again.

The core of the project is the agent tool-use loop and the quality of the ranking prompt and rubric.

### Data

- YouTube Data API: video search and metadata (public and free, needs an API key)
- `youtube-transcript-api`: video transcripts (public and free)

### Risks

Some videos have no transcript, and YouTube may block transcript requests from time to time. There should still be enough data to get started and iterate on.

### Validation

I will rank 10 to 15 videos by hand first, then compare the agent's rankings to mine.

### Scope and Complexity

Medium. The required part is the agent tool-use loop and the prompt and rubric quality. FastAPI, Chroma, Docker, and Redis/RQ are optional extras to add at the end. They are not needed to finish the project.

## Setup

1. Install uv if you don't have it yet: https://docs.astral.sh/uv/getting-started/installation/

2. Clone this repository (or download the zip and extract it).

3. Create a `.env` file from the template and add your API key:

       cp .env.example .env

4. Install dependencies:

       uv sync

5. Start Jupyter:

       uv run jupyter notebook

## Notebooks

- `notebooks/01-setup.ipynb` - smoke test that confirms your environment works
- `notebooks/02-rag.ipynb` - a minimal RAG baseline you can adapt to your own data

## Data

Put your project data in the `data/` folder. See `notebooks/02-rag.ipynb` for how to load it.
