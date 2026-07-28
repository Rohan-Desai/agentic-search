"""Deterministic enforcement for request-scoped research tool budgets."""
from __future__ import annotations

from typing import Protocol, TypeVar

from app.models.research import ResearchContext


class EvidenceLike(Protocol):
    doc_id: str
    chunk_id: str
    text: str


EvidenceValue = TypeVar("EvidenceValue", bound=EvidenceLike)


def reserve_tool_call(
    context: ResearchContext,
    *,
    search: bool = False,
) -> str | None:
    """Reserve one allowed tool call or return a stable limit code."""

    if context.usage.tool_calls >= context.budget.max_tool_calls:
        return "tool_budget_exhausted"
    if search and context.usage.searches >= context.budget.max_searches:
        return "search_budget_exhausted"
    if (
        search
        and context.usage.consecutive_no_progress
        >= context.budget.no_progress_limit
    ):
        return "no_progress_limit_reached"

    context.usage.tool_calls += 1
    if search:
        context.usage.searches += 1
    return None


def select_within_evidence_budget(
    context: ResearchContext,
    values: list[EvidenceValue],
) -> tuple[list[EvidenceValue], str | None]:
    """Keep canonical duplicates and only new evidence that fits both limits."""

    existing_sources = {
        (item.doc_id, item.chunk_id) for item in context.evidence
    }
    remaining_items = context.budget.max_evidence - context.usage.evidence_count
    remaining_chars = (
        context.budget.max_context_chars - context.usage.context_chars
    )
    selected: list[EvidenceValue] = []
    limit_code: str | None = None

    for value in values:
        source = (value.doc_id, value.chunk_id)
        if source in existing_sources:
            selected.append(value)
            continue
        if remaining_items <= 0:
            limit_code = "evidence_budget_exhausted"
            continue
        if len(value.text) > remaining_chars:
            limit_code = "context_budget_exhausted"
            continue

        selected.append(value)
        existing_sources.add(source)
        remaining_items -= 1
        remaining_chars -= len(value.text)

    return selected, limit_code


def record_search_progress(context: ResearchContext, new_evidence_count: int) -> None:
    """Track consecutive searches that add no canonical evidence."""

    if new_evidence_count:
        context.usage.consecutive_no_progress = 0
    else:
        context.usage.consecutive_no_progress += 1
