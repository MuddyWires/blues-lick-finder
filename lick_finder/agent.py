from dataclasses import dataclass

from jaxn import JSONParserHandler, StreamingJSONParser
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent

from .tools import LickFinderTools


class AgentResponse(BaseModel):
    answer: str


AGENT_INSTRUCTIONS = """
You're a blues guitar teacher helping a student find well-taught lesson
videos and track what they practice. You have seven tools: search_lessons,
save_lesson, get_history, open_lesson, like_lesson, queue_topic, and
change_saved_lesson.

Tool choice:
- search_lessons: the first step for any "find me a lesson" request, or a
  request for licks/techniques you don't already have in the practice
  history. If the user asked for a specific level, pass it as `level`.
  Every result has a stored `level`; use it for ranking and for
  save_lesson's `level`. Say "unclear" when it is, don't guess.
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
- change_saved_lesson: call it when the user asks to delete or edit a saved
  lesson, or to un-like one. It does nothing and returns a "not supported"
  message: tell the user that in one sentence. Never say the change was
  made, and don't check get_history first.

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

Each result's `level` (beginner / intermediate / advanced / unclear) is
precomputed. Use it as given, don't re-estimate it.

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
    model: str = "openai:gpt-5.4-mini"
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
        tools.change_saved_lesson,
    ]

    return Agent(
        name=config.name,
        model=config.model,
        instructions=config.instructions,
        tools=agent_tools,
    )


class AnswerStreamHandler(JSONParserHandler):
    def on_value_chunk(self, path: str, field_name: str, chunk: str) -> None:
        if path == '' and field_name == 'answer':
            print(chunk, end='', flush=True)


class AgentStreamRunner:
    """Streams the answer as it's generated and prints each tool call as it
    happens, the same pattern as `AgentStreamRunner` in the course's
    documentation-agent example."""

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
