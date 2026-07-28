"""Agent-driven document search using the OpenAI Agents SDK tool loop."""
from __future__ import annotations

from uuid import uuid4

from agents import Agent, Runner, set_default_openai_key

from app.agents.base import default_model
from app.agents.research_tools import AGENTIC_RESEARCH_TOOLS, AgentToolContext
from app.core.config import get_settings
from app.models.research import (
    AgentAnswer,
    AgentAnswerOutcome,
    ResearchContext,
)
from app.models.schemas import ConversationTurn, SearchMode, SearchResponse

AGENT_INSTRUCTIONS = """
Answer questions using only evidence returned by the document tools.

- Decide which searches to run and reformulate when results are weak or incomplete.
- Search separately for materially different parts of a multi-part question.
- Inspect nearby context when a passage may be missing a qualification.
- Cite supporting evidence IDs inline as [E1], [E2], and so on.
- Never invent an evidence ID or use outside knowledge.
- If reasonable searches do not find the answer, return outcome "not_found".
- If ambiguity would materially change the answer, ask one focused question and
  return outcome "clarification".
- Otherwise return outcome "answered".
- Stop when the evidence supports the answer or further searching would repeat
  the same information.
""".strip()


def build_agent() -> Agent[AgentToolContext]:
    """Create the single agent used by agentic search."""

    return Agent[AgentToolContext](
        name="Agentic Search",
        model=default_model(),
        instructions=AGENT_INSTRUCTIONS,
        tools=AGENTIC_RESEARCH_TOOLS,
        output_type=AgentAnswer,
    )


def build_agent_input(
    query: str,
    history: list[ConversationTurn] | None,
) -> str:
    """Render history and the current question for multi-turn resolution."""

    lines = ["Conversation history:"]
    if history:
        lines.extend(f"{turn.role.upper()}: {turn.content}" for turn in history)
    else:
        lines.append("(none)")
    lines.extend(["", "Current question:", query])
    return "\n".join(lines)


async def run_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
) -> SearchResponse:
    """Let one agent search until it is ready to answer."""

    settings = get_settings()
    set_default_openai_key(settings.openai_api_key, use_for_tracing=False)

    context = ResearchContext(
        request_id=uuid4().hex,
        original_query=query,
        history=list(history or []),
        authorized_doc_ids=doc_ids,
    )
    tool_context = AgentToolContext.create(context)
    result = await Runner.run(
        build_agent(),
        build_agent_input(query, history),
        context=tool_context,
        max_turns=context.budget.max_turns,
    )
    output = AgentAnswer.model_validate(result.final_output)

    return SearchResponse(
        query=query,
        mode=SearchMode.AGENTIC,
        answer=output.answer,
        citations=[],
        steps=[],
        clarification_needed=output.outcome is AgentAnswerOutcome.CLARIFICATION,
        answer_found=output.outcome is AgentAnswerOutcome.ANSWERED,
    )
