"""End-to-end orchestration for agentic document search."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.agents.research_agent import (
    ResearchRunResult,
    run_structured_research,
)
from app.agents.research_repair import (
    ValidatedResearchRunResult,
    validate_and_repair_research,
)
from app.models.schemas import ConversationTurn, SearchResponse
from app.services.research_response_service import build_validated_search_response
from app.services.research_trace_service import build_operational_steps

ResearchCallable = Callable[..., Awaitable[ResearchRunResult]]
ValidationCallable = Callable[
    [ResearchRunResult],
    Awaitable[ValidatedResearchRunResult],
]


async def execute_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
    *,
    research: ResearchCallable = run_structured_research,
    validate_and_repair: ValidationCallable = validate_and_repair_research,
) -> SearchResponse:
    """Execute research, correction, validation, and public projection."""

    research_result = await research(
        query,
        top_k=top_k,
        doc_ids=doc_ids,
        history=history,
    )
    validated_result = await validate_and_repair(research_result)
    response = build_validated_search_response(
        query=query,
        output=validated_result.output,
        context=validated_result.context,
    )
    response.steps = build_operational_steps(
        validated_result.context,
        repair_attempted=validated_result.repair_attempted,
    )
    return response


async def run_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
) -> SearchResponse:
    """Run the production agentic-search pipeline."""

    return await execute_agentic_search(
        query=query,
        top_k=top_k,
        doc_ids=doc_ids,
        history=history,
    )
