from pydantic import BaseModel, Field
from pydantic_ai import Agent

from tests.cost_tracker import capture_usage
from tests.utils import collect_tool_returns, collect_tools, get_model_name

JUDGE_MODEL = "openai:gpt-5.4-nano"

judge_instructions = """
You are an expert judge evaluating the performance of an AI agent.
Judge each criterion only from the evidence you are given: the agent's final
output, its tool calls, and the results those tools returned. If the evidence
needed to check a criterion is missing, the criterion fails. Quote the exact
evidence in your judgement.
""".strip()


class JudgeCriterion(BaseModel):
    """
    Evaluation of a single test requirement or behavioral rule.
    """
    criterion_description: str = Field(
        description="The specific requirement or rule that the agent is being evaluated against."
    )
    passed: bool = Field(
        description="Indicates whether the agent's response and actions successfully satisfied this requirement."
    )
    judgement: str = Field(
        description="A clear explanation of why the agent passed or failed, referencing specific evidence from the agent's output, tool calls or tool results."
    )


class JudgeFeedback(BaseModel):
    """
    The complete evaluation report from the judge agent, summarizing performance across all criteria.
    """
    criteria: list[JudgeCriterion] = Field(
        description="A collection of individual evaluations for each performance requirement provided in the test."
    )
    feedback: str = Field(
        description="A holistic summary of the agent's performance, providing overall context and identifying key strengths or failures."
    )


def create_judge_agent():
    agent = Agent(
        name="judge",
        model=JUDGE_MODEL,
        instructions=judge_instructions,
        output_type=JudgeFeedback
    )
    return agent


judge_user_prompt_template = """
Evaluate the agent's performance based on the following criteria:
<CRITERIA>
{criteria}
</CRITERIA>

The agent's final output was:
<AGENT_OUTPUT>
{output}
</AGENT_OUTPUT>

Tool calls:
<TOOL_CALLS>
{tool_calls}
</TOOL_CALLS>

What the tools returned:
<TOOL_RESULTS>
{tool_results}
</TOOL_RESULTS>
""".strip()


async def judge(criteria, output, tool_calls, tool_results):
    """Run the judge on plain strings, so it can also be tested on its own."""
    judge_agent = create_judge_agent()
    judge_user_prompt = judge_user_prompt_template.format(
        criteria='\n'.join(criteria),
        output=output,
        tool_calls='\n'.join(tool_calls),
        tool_results='\n'.join(tool_results),
    )

    judge_result = await judge_agent.run(judge_user_prompt)
    capture_usage(get_model_name(judge_agent), judge_result)

    return judge_result.output


async def assert_criteria(result, criteria):
    messages = result.new_messages()

    feedback = await judge(
        criteria,
        output=result.output.model_dump_json(),
        tool_calls=[str(tc) for tc in collect_tools(messages)],
        tool_results=[str(tr) for tr in collect_tool_returns(messages)],
    )

    print('judge feedback:')
    print(feedback.feedback)

    for criterion in feedback.criteria:
        print(f"{criterion.criterion_description}: {criterion.judgement}")
        assert criterion.passed, f"{criterion.criterion_description}: {criterion.judgement}"
