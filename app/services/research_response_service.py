"""Project validated internal research state into the public API contract."""
from __future__ import annotations

from app.models.research import (
    EvidenceRecord,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
)
from app.models.schemas import Citation, SearchMode, SearchResponse
from app.services.grounding_validator import validate_research_output

_CITATION_SNIPPET_CHARS = 200


class UnpublishableResearchError(ValueError):
    """Raised when an invalid internal proposal reaches publication."""


def build_validated_search_response(
    *,
    query: str,
    output: ResearchAgentOutput,
    context: ResearchContext,
    mode: SearchMode = SearchMode.AGENTIC,
) -> SearchResponse:
    """Build a public response only from deterministically validated state."""

    validation = validate_research_output(context, output)
    if not validation.valid:
        raise UnpublishableResearchError(
            "Research output failed grounding validation and cannot be published."
        )

    evidence_by_id = {item.evidence_id: item for item in context.evidence}
    citation_ids = _claim_evidence_ids(output)
    missing_ids = [
        evidence_id for evidence_id in citation_ids if evidence_id not in evidence_by_id
    ]
    if missing_ids:
        raise UnpublishableResearchError(
            "Validated output references evidence missing from the current context."
        )

    citations = [
        _to_public_citation(evidence_by_id[evidence_id])
        for evidence_id in citation_ids
    ]
    return SearchResponse(
        query=query,
        mode=mode,
        answer=output.answer,
        citations=citations,
        steps=[],
        clarification_needed=output.outcome is ResearchOutcome.CLARIFICATION,
        answer_found=output.outcome
        in {ResearchOutcome.COMPLETE, ResearchOutcome.PARTIAL},
        partial=output.outcome is ResearchOutcome.PARTIAL,
    )


def _claim_evidence_ids(output: ResearchAgentOutput) -> list[str]:
    """Return unique evidence IDs in material-claim order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for claim in output.claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in seen:
                seen.add(evidence_id)
                ordered.append(evidence_id)
    return ordered


def _to_public_citation(evidence: EvidenceRecord) -> Citation:
    scores = [
        item.retrieval_score
        for item in evidence.discoveries
        if item.retrieval_score is not None
    ]
    return Citation(
        doc_id=evidence.doc_id,
        filename=evidence.filename,
        chunk_id=evidence.chunk_id,
        snippet=evidence.text[:_CITATION_SNIPPET_CHARS],
        score=max(scores, default=None),
        page=evidence.location.page,
        sheet=evidence.location.sheet,
        section=evidence.location.section,
    )
