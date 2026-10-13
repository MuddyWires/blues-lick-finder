#!/usr/bin/env python
# coding: utf-8
#
# Standalone script version of notebooks/02-rag.ipynb up through the agent
# definition, plus a demo run of three queries for the capstone submission.
# Run with: .venv/bin/python scratchpad/agent_demo.py
#
# Uses scratch copies of practice_log/topics so it doesn't touch the real
# data/practice_log.json or data/topics.txt.

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks"))

#!/usr/bin/env python
# coding: utf-8

# # Blues Lick Finder: RAG Baseline
# 
# A minimal RAG baseline over blues guitar lesson videos, following the same structure we used in the module: a `search` function, a `build_prompt` function, an `llm` function, and a top-level `rag` function that chains them together.
# 
# Given a song or technique, it retrieves candidate lessons and asks the LLM to rank them by teaching quality.

# In[1]:


import json

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from minsearch import Index
from gitsource import chunk_documents

openai_client = OpenAI()


# ## 1. Load Your Data
# 
# Each document is one YouTube lesson video: metadata from a `yt-dlp` search (no API key needed) plus the English transcript from `youtube-transcript-api` when one exists. Each video also gets its top 20 viewer comments by likes, excluding the creator's own.
# 
# The first run fetches from YouTube and caches everything to `data/lessons.json`. Later runs load from that file. Delete it to re-fetch.
# 
# The fetching code lives in `youtube_data.py` next to this notebook.

# In[2]:


from youtube_data import load_lessons

documents = load_lessons()

with_transcript = sum(1 for d in documents if d["transcript"])
with_comments = sum(1 for d in documents if d["comments"])
print(f"Loaded {len(documents)} lessons, {with_transcript} with transcripts, {with_comments} with comments")


# ## 2. Build the Index
# 
# Transcripts are long, so we split them into overlapping chunks with `chunk_documents` (3000 characters, step 1500), the same way we did in class, and index the chunks instead of whole videos. Each chunk keeps its video's metadata. Videos without a transcript are skipped.
# 
# minsearch builds an in-memory TF-IDF index over the fields you specify.

# In[3]:


transcript_docs = [doc for doc in documents if doc["transcript"]]
document_chunks = chunk_documents(
    transcript_docs, size=3000, step=1500, content_field_name="transcript"
)
print(f"{len(transcript_docs)} videos -> {len(document_chunks)} chunks")

index = Index(
    text_fields=["title", "description", "tags", "content"],
    keyword_fields=["video_id", "channel", "topic"],
)

index.fit(document_chunks)


# ## 3. Define the RAG Functions
# 
# `search` retrieves relevant documents, `build_prompt` formats them into a prompt, `llm` calls the model, and `rag` chains all three.

# In[4]:


def search(query):
    results = index.search(query, num_results=50)

    # Results are sorted best-first and may hold several chunks of the same
    # video. Keep only the first (best) chunk per video so we return 5
    # different videos.
    best_chunk_per_video = {}
    for chunk in results:
        best_chunk_per_video.setdefault(chunk["video_id"], chunk)

    return list(best_chunk_per_video.values())[:5]


# In[ ]:


instructions = """
You're a blues guitar teacher helping a student find the best lesson videos
for the song or technique in their QUERY. YouTube ranks videos by engagement;
your job is to rank them by teaching quality instead.

Rank exactly the candidates in the CONTEXT. Never add, repeat, or rename a
lesson that isn't one of the candidates.

Use only the candidate lessons in the CONTEXT. Skip candidates that aren't
about the requested song or technique. Rank the rest from best to worst
using this rubric, judged mostly from each candidate's `content` field,
which is the part of the video's transcript that best matches the QUERY:

- Breakdown: splits the lick into small, clearly explained pieces
- Demonstration: plays it slowly before playing it at full speed
- Specifics: names frets, strings, fingers, or points to tab/notation
- Why: explains the theory or feel (scale, chord tones, phrasing) behind it
- Focus: the excerpt teaches the lick instead of intros or sales pitches

Each candidate also has a `comments` field with its most-liked viewer
comments and like counts. Use comments that talk about the teaching (pace,
clarity, tabs, how quickly it gets going, mistakes) as extra evidence for
the rubric. Ignore general praise, jokes, and song requests. An empty list
means no comments are available. Missing or empty comments are neutral:
never lower a score just because a video has no comments.

When you use a comment, quote it word for word with its like count. Never
describe or summarize what viewers said without quoting them, and never
claim something about the comments that no comment actually says.

Also estimate the lesson's level from the title, tags, transcript excerpt,
and comments:

- beginner: explains basics like what a bend or the pentatonic box is,
  plays very slowly, or says it's for people starting out
- intermediate: assumes the pentatonic box and basic bends are known and
  focuses on phrasing, licks in context, and following the chord changes
- advanced: chord-tone soloing, fast or complex runs, little explanation
  of the basics

Give one short reason for the level, quoting the transcript or a comment
when you can. If there isn't enough to tell, say "unclear" instead of
guessing.

For each ranked lesson, return: rank, title, channel, URL, a score from 1 to 5,
a one-sentence justification that cites the rubric, viewer evidence (1-2
quoted comments with like counts, or "none" if no comment is about the
teaching), level with a short reason, and practice-log tags. Tags are real
values, not field names, e.g. "Tags: BB King box, bending, key of A".
Include a key only if a candidate names one. If none of the candidates fit
the QUERY, say so.
""".strip()


def build_prompt(query, search_results):
    search_result_json = json.dumps(search_results, indent=2)

    user_prompt = f"""
<QUERY>
{query}
</QUERY>

<CONTEXT>
{search_result_json}
</CONTEXT>
""".strip()

    return user_prompt


# In[6]:


def llm(user_prompt, instructions=None, model='gpt-4o-mini'):
    messages = []

    if instructions is not None:
        messages.append({
            "role": "system",
            "content": instructions
        })

    messages.append({
        "role": "user",
        "content": user_prompt
    })

    response = openai_client.responses.create(
        model=model,
        input=messages
    )

    return response.output_text


# In[7]:


def rag(query):
    search_results = search(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt, instructions)
    return answer


# ## 4. Try It Out

# In[8]:


print(rag("Which lessons teach the BB King box licks best?"))


# ## 5. Agent Tools
# 
# `rag()` above always runs the same three steps. The agent instead gets six small tools and decides which ones a message needs: `search_lessons`, `save_lesson`, `get_history`, `open_lesson`, `like_lesson`, and `queue_topic`.
# 
# They're bundled in one `LickFinderTools` class, the same way `SearchTools` bundles `search`/`get_file` in the course's documentation-agent example. pydantic_ai builds each tool's schema from the method's type hints and docstring, so there's no manual JSON schema to write.

# In[ ]:


from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from youtube_data import TOPICS_PATH

PRACTICE_LOG_PATH = TOPICS_PATH.parent / "practice_log.json"


class LickFinderTools:
    """
    Searches stored blues lessons and manages a personal practice history.
    """

    def __init__(self, practice_log_path: Path = PRACTICE_LOG_PATH, topics_path: Path = TOPICS_PATH):
        self.practice_log_path = practice_log_path
        self.topics_path = topics_path
        self._lock = Lock()

    def _read_log(self):
        if self.practice_log_path.exists():
            return json.loads(self.practice_log_path.read_text())
        return []

    def _write_log(self, entries):
        self.practice_log_path.write_text(json.dumps(entries, indent=2))

    def search_lessons(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the stored blues lesson videos. The first step for any "find
        me a lesson" request.

        Args:
            query: The song or technique to search for.
        """
        return search(query)

    def save_lesson(self, video_id: str, song: str, technique: str, key: str, level: str):
        """
        Save a lesson to the practice history. Call only when the user
        chooses a specific lesson (e.g. "I'll practice this one"), never
        automatically after a search. Rejects duplicates.

        Args:
            video_id: The video's video_id from search results.
            song: The song the lesson teaches, or "" if general.
            technique: The technique the lesson teaches, e.g. "string bending".
            key: The musical key, or "" if none is named.
            level: Your estimate of the lesson's level.
        """
        with self._lock:
            entries = self._read_log()
            if any(e["video_id"] == video_id for e in entries):
                return "already saved"

            entry = {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "song": song,
                "technique": technique,
                "key": key,
                "level": level,
                "saved_date": date.today().isoformat(),
                "liked": False,
                "view_count": 0,
                "last_viewed": None,
            }
            entries.append(entry)
            self._write_log(entries)
            return entry

    def get_history(self, filter: Optional[str] = None, liked_only: bool = False, limit: int = 10):
        """
        List saved lessons, newest first. Use for questions about what's
        already saved, what to practice next, or to find a lesson to replay.

        Args:
            filter: Text to match against song, technique, or key. Omit to
                list everything.
            liked_only: Only return liked lessons.
            limit: Max entries to return.
        """
        entries = self._read_log()

        if liked_only:
            entries = [e for e in entries if e["liked"]]

        if filter:
            needle = filter.lower()
            entries = [
                e for e in entries
                if needle in " ".join(str(e.get(f, "")) for f in ("song", "technique", "key")).lower()
            ]

        entries.sort(key=lambda e: e["saved_date"], reverse=True)
        return entries[:limit]

    def open_lesson(self, video_id: str):
        """Replay a saved lesson and record the view.

        Args:
            video_id: The video_id of the saved lesson to replay.
        """
        with self._lock:
            entries = self._read_log()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["view_count"] += 1
                    entry["last_viewed"] = date.today().isoformat()
                    self._write_log(entries)
                    return {"url": entry["url"], "view_count": entry["view_count"]}
            return f"video {video_id} is not in the practice history"

    def like_lesson(self, video_id: str):
        """Mark a saved lesson as liked.

        Args:
            video_id: The video_id of the saved lesson to like.
        """
        with self._lock:
            entries = self._read_log()
            for entry in entries:
                if entry["video_id"] == video_id:
                    entry["liked"] = True
                    self._write_log(entries)
                    return entry
            return f"video {video_id} is not in the practice history"

    def queue_topic(self, topic: str) -> str:
        """
        Queue a new search topic for the next data fetch, when
        search_lessons finds nothing relevant. Does not fetch immediately.

        Args:
            topic: The topic to queue, phrased like a YouTube search.
        """
        with self._lock:
            existing = [
                line.strip() for line in self.topics_path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if topic.strip().lower() in (line.lower() for line in existing):
                return "already queued"

            with self.topics_path.open("a") as f:
                f.write(f"{topic}\n")
            return "queued"


_SCRATCH_DIR = Path(__file__).resolve().parent
_SCRATCH_DIR.joinpath("topics_scratch.txt").write_text(
    (_SCRATCH_DIR.parent / "data" / "topics.txt").read_text()
)
_SCRATCH_DIR.joinpath("practice_log_scratch.json").write_text("[]")

lick_finder_tools = LickFinderTools(
    practice_log_path=_SCRATCH_DIR / "practice_log_scratch.json",
    topics_path=_SCRATCH_DIR / "topics_scratch.txt",
)


# ## 6. Agent
# 
# Ranking lessons by teaching quality stays the LLM's job, guided by the same rubric `instructions` used above, now folded into the agent's instructions alongside the rules for when to use each tool.

# In[ ]:


from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent


class AgentResponse(BaseModel):
    answer: str


AGENT_INSTRUCTIONS = """
You're a blues guitar teacher helping a student find well-taught lesson
videos and track what they practice. You have six tools: search_lessons,
save_lesson, get_history, open_lesson, like_lesson, and queue_topic.

Tool choice:
- search_lessons: the first step for any "find me a lesson" request, or a
  request for licks/techniques you don't already have in the practice
  history. If the user asked for a specific level, mention it in the
  query text and judge the actual level yourself from the results.
- save_lesson: call ONLY when the user chooses a specific lesson (e.g.
  "I'll practice this one", "save the first one"). Never save automatically
  just because you recommended it in a search. Fill `song`, `technique`,
  `key`, and `level` from the video's own metadata and transcript, not from
  the user's query.
- get_history: use for questions about what's already saved, what to
  practice next, or to find a lesson to replay. Use `filter` for a song,
  technique, or key; `liked_only` for "what did I like"; omit both to list
  everything.
- open_lesson: use when the user wants to revisit a lesson already in their
  history. Look it up with get_history first if you don't already have its
  video_id.
- like_lesson: use after the user says they practiced and liked a saved
  lesson, not just because they watched it.
- queue_topic: call when search_lessons returns nothing relevant to the
  request. This does not fetch anything right away — tell the user you've
  queued it and they should check back after the next data fetch.

Ranking search_lessons results (the rubric):
Rank exactly the candidates search_lessons returns. Never add, repeat, or
rename a lesson that isn't one of them. Skip candidates that aren't about
the requested song or technique. Rank the rest from best to worst using:

- Breakdown: splits the lick into small, clearly explained pieces
- Demonstration: plays it slowly before playing it at full speed
- Specifics: names frets, strings, fingers, or points to tab/notation
- Why: explains the theory or feel (scale, chord tones, phrasing) behind it
- Focus: the excerpt teaches the lick instead of intros or sales pitches

Each candidate's `comments` field holds its most-liked viewer comments.
Use comments about the teaching (pace, clarity, tabs, mistakes) as extra
evidence. Ignore general praise, jokes, and song requests. When you use a
comment, quote it word for word with its like count. Missing or empty
comments are neutral, never a reason to lower a score.

Estimate each lesson's level (beginner / intermediate / advanced /
unclear) the same way for ranking and for save_lesson's `level` input: from
its title, tags, transcript excerpt, and comments. If there isn't enough to
tell, say "unclear" instead of guessing.

Timestamps: give a timestamp only if a viewer comment states one, quoted
word for word. Never guess or estimate a timestamp yourself.

Suggesting what to practice (from get_history, no extra tool):
- saved, never viewed -> "you haven't started this one"
- viewed recently, not liked yet -> "still learning, keep going"
- liked, not viewed in 2+ weeks -> "worth a refresh"

General:
- Only me uses this agent for now.
- Be concise. Answer the question asked; don't dump the full rubric unless
  you're ranking lessons.
""".strip()


@dataclass
class LickFinderAgentConfig:
    model: str = "openai:gpt-4o-mini"
    name: str = "lick_finder"
    instructions: str = AGENT_INSTRUCTIONS


def create_agent(config: LickFinderAgentConfig, tools: LickFinderTools) -> Agent:
    agent_tools = [
        tools.search_lessons,
        tools.save_lesson,
        tools.get_history,
        tools.open_lesson,
        tools.like_lesson,
        tools.queue_topic,
    ]

    return Agent(
        name=config.name,
        model=config.model,
        instructions=config.instructions,
        tools=agent_tools,
    )


lick_finder_agent = create_agent(LickFinderAgentConfig(), lick_finder_tools)


# ## 7. Agent Loop
# 
# Streams the answer as it's generated and prints each tool call as it happens, the same pattern as `AgentStreamRunner` in the course's documentation-agent example.

# In[ ]:


from jaxn import JSONParserHandler, StreamingJSONParser
from pydantic_ai.messages import FunctionToolCallEvent


class AnswerStreamHandler(JSONParserHandler):
    def on_value_chunk(self, path: str, field_name: str, chunk: str) -> None:
        if path == '' and field_name == 'answer':
            print(chunk, end='', flush=True)


class AgentStreamRunner:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def run(self, user_prompt: str, message_history=None):
        if message_history is None:
            message_history = []

        async with self.agent.iter(
            user_prompt,
            message_history=message_history,
            output_type=AgentResponse,
        ) as agent_run:
            async for node in agent_run:
                if Agent.is_model_request_node(node):
                    await self._stream_answer(node, agent_run)
                elif Agent.is_call_tools_node(node):
                    await self._print_tool_calls(node, agent_run)

            return agent_run.result

    async def _stream_answer(self, node, agent_run):
        args_so_far = ""
        parser = StreamingJSONParser(AnswerStreamHandler())

        async with node.stream(agent_run.ctx) as stream:
            async for response in stream.stream_response():
                for part in response.parts:
                    if part.part_kind != 'tool-call' or part.tool_name != 'final_result':
                        continue
                    args_new = part.args
                    args_new_chunk = args_new[len(args_so_far):]
                    args_so_far = args_new
                    parser.parse_incremental(args_new_chunk)

    async def _print_tool_calls(self, node, agent_run):
        async with node.stream(agent_run.ctx) as events:
            async for event in events:
                if not isinstance(event, FunctionToolCallEvent):
                    continue
                print(f"\nTOOL CALL: {event.part.tool_name}({event.part.args})")




# --- Demo run: three queries covering different tool paths ---

QUERIES = [
    "Find me a lesson on string bending for beginners.",
    "What have I saved so far?",
    "Delete the BB King box lesson from my history.",
]


async def main():
    runner = AgentStreamRunner(lick_finder_agent)
    for q in QUERIES:
        print("\n" + "=" * 80)
        print(f"QUESTION: {q}")
        print("=" * 80)
        result = await runner.run(q)
        print("\n\nFINAL ANSWER OBJECT:")
        print(result.output if result is not None else None)


asyncio.run(main())
