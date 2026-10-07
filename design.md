# RFC: Agent tools for the Blues Lick Finder

- **Status:** Draft
- **Date:** 2026-10-07
- **Scope:** Tool design for turning the week 1 RAG pipeline into a tool-calling agent. No code yet.

## Summary

Replace the fixed `rag()` pipeline with an agent loop that calls tools. The agent gets six small tools: one to search stored lessons, four to manage a personal practice history, and one to queue new topics for fetching. The smallest useful version uses three of them: `search_lessons`, `save_lesson`, and `get_history`.

## Motivation

The week 1 notebook (`notebooks/02-rag.ipynb`) always runs the same steps: `search` → `build_prompt` → `llm`. That answers "find me lessons for X", but not the tracker half of the project: remembering which lessons I chose, which ones I liked, and what to practice next. An agent can decide which of these actions a message needs.

In the agent, `rag()` goes away. `search` becomes a tool, and `build_prompt` / `llm` become the agent loop. Ranking lessons by teaching quality stays the LLM's job, guided by the rubric in the system prompt.

## Example requests

These are the messages the agent must handle, chosen by the user:

| | Request | Needs |
|---|---|---|
| a | "Find me the best lesson for the Hide Away intro." | search |
| b | "Easy BB King licks, I'm a beginner." | search filtered by level |
| c | "Show me the lick at the start of the Pride and Joy solo." | search; a timestamp only if a viewer comment gives one |
| f | "What have I saved for string bending?" | history |
| g | "What should I practice today?" | history with views and likes |
| h | "Find more lessons like the one I liked last week." | history (liked) + search |
| — | "Easy mixolydian blues lick." | search; the LLM can explain the theory itself |
| — | "Magic Sam beginner licks." | search; likely not in the data yet, so queue the topic |

Users: only me for now, other people later.

## Proposal: tools

| # | Tool | Description | Inputs → Returns | Priority |
|---|---|---|---|---|
| 1 | `search_lessons` | Searches the stored lessons. The first step for any "find me…" request. | `query`, optional `level` → 5 videos, each with its best transcript chunk, metadata, and comments | Essential |
| 2 | `save_lesson` | Saves a lesson to the practice history, only when the user chooses it ("I'll practice this one"). Rejects duplicates. | `video_id`, `song`, `technique`, `key`, `level` → the saved entry with today's date, or "already saved" | Essential |
| 3 | `get_history` | Lists saved lessons, optionally filtered. Used for f, g, h, and for finding a lesson to replay. | optional `filter` (text or tag), `liked_only`, `limit` → entries with URL, saved date, liked, view count, last viewed; newest first | Essential |
| 4 | `open_lesson` | Replays (revisits) a saved lesson and records the view. | `video_id` → URL and updated view count | Small; needed for g |
| 5 | `like_lesson` | Marks a saved lesson as liked, usually after practicing it. | `video_id` → updated entry | Small; needed for h |
| 6 | `queue_topic` | Adds a search topic to `data/topics.txt` when `search_lessons` finds nothing relevant. | `topic` → "queued" or "already queued" | Nice to have |

### How the agent handles "what should I practice today?" (g)

No extra tool. The agent calls `get_history` and infers a suggestion from the saved date, views, and likes:

- saved, never viewed → "you haven't started this one"
- viewed recently, not liked yet → "still learning, keep going"
- liked, not viewed in 2+ weeks → "worth a refresh"

## Design decisions

- **Search and YouTube fetching are separate.** Searching stored data takes milliseconds and always works. Fetching from YouTube takes 1–3 minutes per topic and can be blocked. One combined tool would make every search slow and fragile.
- **New topics are queued, not fetched live.** Waiting minutes in a chat is a bad experience. `queue_topic` appends to `data/topics.txt`, which `youtube_data.py` already reads. Trade-off: a new topic gets no answer in the same conversation, so the agent must say so ("Nothing on Magic Sam yet. I've queued it, try again after the next fetch").
- **Only chosen lessons are saved.** The agent doesn't log every recommendation, so the history reflects what I actually practice.
- **Saving and liking are separate tools.** You save a lesson when you pick it, but only know if you like it after practicing.
- **Replay goes through a tool.** Opening a URL directly would work, but the agent could not record the view, and (g) depends on views.
- **No `user_id` yet.** History lives in one file (e.g. `data/practice_log.json`). When other users arrive, `user_id` becomes one extra input on tools 2–5.

## Alternatives rejected

- **`rank_lessons` tool:** a second LLM call to rank would duplicate what the agent's own LLM already does with the rubric.
- **Separate history tools per filter** (`get_by_song`, `get_by_tag`, …): one `get_history` with an optional filter is enough.
- **`search_lessons` fetching from YouTube on its own:** hides slow, failure-prone work inside what looks like a fast search.
- **`replay_lesson` that only returns a URL:** replaced by `open_lesson`, which also records the view.
- **A "theory" tool for questions like mixolydian:** the LLM can explain theory without a tool.

## Data prerequisites

One feature needs data the current fetch code (`notebooks/youtube_data.py`) doesn't store yet:

| Data | Needed for | Work | Re-fetch from YouTube? |
|---|---|---|---|
| `level` per video (beginner / intermediate / advanced / unclear) | `search_lessons(level=...)`, requests b and "Magic Sam beginner licks" | One LLM call per video over title, tags, start of transcript, and comments; add `level` to the index's `keyword_fields` | No |

Timestamps are out of scope. The agent gives a timestamp only when a viewer comment states it, quoted word for word, and never guesses one.

## Rollout

1. **Day 1:** `search_lessons`, `save_lesson`, `get_history` (covers a, b once levels exist, c roughly, f, g in a basic form).
2. **Next:** `open_lesson` and `like_lesson` (full g and h).
3. **Then:** `queue_topic`.
4. **In parallel:** compute a level for each video.

## Open questions

- How should the agent choose between several valid suggestions for (g)? Start with the three rules above and adjust after real use.
- Should `get_history` also return a lesson's transcript chunk or comments, or only the saved entry? Start with the saved entry only.
