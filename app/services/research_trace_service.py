"""Build concise public operational steps from trusted research state."""
from __future__ import annotations

from app.models.research import RequirementStatus, ResearchContext
from app.models.schemas import AgentStep

_MAX_QUERY_CHARS = 160


def build_operational_steps(
    context: ResearchContext,
    *,
    repair_attempted: bool,
) -> list[AgentStep]:
    """Summarize application-observed actions without exposing reasoning."""

    steps = [_attempt_step(attempt) for attempt in context.attempts]
    supported = sum(
        item.status is RequirementStatus.SUPPORTED
        for item in context.requirements
    )
    total = len(context.requirements)
    detail = (
        f"stop={context.stop_reason.value if context.stop_reason else 'unknown'}; "
        f"requirements_supported={supported}/{total}; "
        f"evidence={len(context.evidence)}; "
        f"repair={'yes' if repair_attempted else 'no'}"
    )
    steps.append(AgentStep(kind="outcome", name="research_complete", detail=detail))
    return steps


def _attempt_step(attempt) -> AgentStep:
    details = [f"status={attempt.status.value}"]
    if attempt.query:
        normalized_query = " ".join(attempt.query.split())
        if len(normalized_query) > _MAX_QUERY_CHARS:
            normalized_query = normalized_query[: _MAX_QUERY_CHARS - 1] + "…"
        details.append(f"query={normalized_query}")
    details.append(f"results={len(attempt.result_evidence_ids)}")
    details.append(f"new_evidence={attempt.new_evidence_count}")
    if attempt.error_code:
        details.append(f"error={attempt.error_code}")
    if attempt.duration_ms is not None:
        details.append(f"duration_ms={attempt.duration_ms}")
    return AgentStep(
        kind="tool",
        name=attempt.tool_name,
        detail="; ".join(details),
    )
