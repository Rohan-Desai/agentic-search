"""Construction and bounded execution of the structured research agent."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from agents import Agent, Runner

from app.agents.base import default_model
from app.agents.research_prompt import RESEARCH_AGENT_INSTRUCTIONS
from app.agents.research_tools import AGENTIC_RESEARCH_TOOLS, AgentToolContext
from app.models.research import (
    ResearchAgentOutput,
    ResearchBudget,
    ResearchContext,
)
from app.models.schemas import ConversationTurn
from app.services.retrieval_service import SearchStore

RunCallable = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ResearchRunResult:
    """The proposed output plus the request-scoped state that produced it."""

    output: ResearchAgentOutput
    context: ResearchContext
    new_items: tuple[Any, ...]


def build_research_agent(*, model: str | None = None) -> Agent[AgentToolContext]:
    """Build the model-facing agent without starting a run."""

    return Agent[AgentToolContext](
        name="Document research agent",
        instructions=RESEARCH_AGENT_INSTRUCTIONS,
        model=model or default_model(),
        tools=AGENTIC_RESEARCH_TOOLS,
        output_type=ResearchAgentOutput,
    )


def build_research_input(
    query: str,
    history: Sequence[ConversationTurn] | None = None,
) -> str:
    """Render prior conversation and the current question unambiguously."""

    lines = ["Conversation history (oldest first; may be empty):"]
    if history:
        lines.extend(f"{turn.role.upper()}: {turn.content}" for turn in history)
    else:
        lines.append("(none)")
    lines.extend(["", "Current question:", query])
    return "\n".join(lines)


def _apply_agent_output(
    context: ResearchContext,
    output: ResearchAgentOutput,
) -> None:
    """Record the agent's proposal for the later validation slice."""

    context.resolved_query = output.resolved_query
    context.requirements = list(output.requirements)
    context.evidence_assessments = list(output.evidence_assessments)
    context.claims = list(output.claims)
    context.stop_reason = output.stop_reason


async def run_structured_research(
    query: str,
    *,
    history: Sequence[ConversationTurn] | None = None,
    doc_ids: list[str] | None = None,
    budget: ResearchBudget | None = None,
    model: str | None = None,
    store: SearchStore | None = None,
    request_id: str | None = None,
    run: RunCallable = Runner.run,
) -> ResearchRunResult:
    """Run one isolated research request with a hard SDK turn limit.

    Tool limits, search limits, and evidence limits are enforced by the
    request-scoped services. ``max_turns`` gives the SDK loop an additional
    hard ceiling.
    """

    prior_turns = list(history or [])
    context = ResearchContext(
        request_id=request_id or uuid4().hex,
        original_query=query,
        history=prior_turns,
        authorized_doc_ids=doc_ids,
        budget=budget or ResearchBudget(),
    )
    tool_context = AgentToolContext.create(context, store=store)
    agent = build_research_agent(model=model)

    result = await run(
        agent,
        build_research_input(query, prior_turns),
        context=tool_context,
        max_turns=context.budget.max_turns,
    )
    output = ResearchAgentOutput.model_validate(result.final_output)
    _apply_agent_output(context, output)

    raw_responses = getattr(result, "raw_responses", ())
    context.usage.turns = len(raw_responses)

    return ResearchRunResult(
        output=output,
        context=context,
        new_items=tuple(getattr(result, "new_items", ())),
    )
