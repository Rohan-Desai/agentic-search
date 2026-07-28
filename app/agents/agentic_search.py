"""End-to-end orchestration for agentic document search."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agents.exceptions import AgentsException, MaxTurnsExceeded
from openai import APIError
from pydantic import ValidationError

from app.agents.research_agent import (
    ResearchRunResult,
    run_structured_research,
)
from app.agents.research_repair import (
    ValidatedResearchRunResult,
    validate_and_repair_research,
)
from app.models.schemas import ConversationTurn, SearchResponse
from app.models.research import AttemptStatus, ResearchBudget
from app.services.research_response_service import (
    UnpublishableResearchError,
    build_validated_search_response,
)
from app.services.research_trace_service import build_operational_steps

ResearchCallable = Callable[..., Awaitable[ResearchRunResult]]
ValidationCallable = Callable[
    [ResearchRunResult],
    Awaitable[ValidatedResearchRunResult],
]


class AgenticSearchRuntimeError(RuntimeError):
    """A safe, typed failure at the agentic-search application boundary."""

    def __init__(self, code: str, public_message: str, status_code: int) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


async def execute_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
    *,
    research: ResearchCallable = run_structured_research,
    validate_and_repair: ValidationCallable = validate_and_repair_research,
    timeout_seconds: float | None = None,
) -> SearchResponse:
    """Execute research, correction, validation, and public projection."""

    timeout = timeout_seconds or ResearchBudget().timeout_seconds
    try:
        async with asyncio.timeout(timeout):
            research_result = await research(
                query,
                top_k=top_k,
                doc_ids=doc_ids,
                history=history,
            )
            validated_result = await validate_and_repair(research_result)
            if not validated_result.validation.valid:
                failed_tool = any(
                    item.status is AttemptStatus.FAILED
                    for item in validated_result.context.attempts
                )
                if failed_tool:
                    raise AgenticSearchRuntimeError(
                        "retrieval_failed",
                        "Document retrieval failed. Please try again.",
                        502,
                    )
                raise AgenticSearchRuntimeError(
                    "invalid_research_output",
                    "The research result could not be safely validated.",
                    502,
                )

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
    except TimeoutError as exc:
        raise AgenticSearchRuntimeError(
            "research_timeout",
            "Document research timed out. Please try a narrower question.",
            504,
        ) from exc
    except MaxTurnsExceeded as exc:
        raise AgenticSearchRuntimeError(
            "turn_budget_exhausted",
            "Document research reached its processing limit.",
            503,
        ) from exc
    except (UnpublishableResearchError, ValidationError) as exc:
        raise AgenticSearchRuntimeError(
            "invalid_research_output",
            "The research result could not be safely validated.",
            502,
        ) from exc
    except (AgentsException, APIError) as exc:
        raise AgenticSearchRuntimeError(
            "model_provider_failed",
            "The research model is temporarily unavailable.",
            502,
        ) from exc


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
