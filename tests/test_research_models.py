"""Deterministic tests for the internal agentic-research state."""
from datetime import timezone

import pytest
from pydantic import ValidationError

from app.models.research import (
    AnswerRequirement,
    EvidenceLocation,
    EvidenceRecord,
    MaterialClaim,
    ResearchBudget,
    ResearchContext,
    RequirementStatus,
    SearchAttempt,
    StopReason,
)
from app.models.schemas import ConversationTurn


def test_research_context_defaults_are_isolated():
    first = ResearchContext(request_id="req-1", original_query="Question one")
    second = ResearchContext(request_id="req-2", original_query="Question two")

    first.requirements.append(
        AnswerRequirement(requirement_id="r1", description="Find the reported revenue")
    )
    first.usage.searches += 1

    assert second.requirements == []
    assert second.usage.searches == 0
    assert first.started_at.tzinfo == timezone.utc


def test_research_budget_rejects_non_positive_limits():
    with pytest.raises(ValidationError):
        ResearchBudget(max_searches=0)

    with pytest.raises(ValidationError):
        ResearchBudget(timeout_seconds=0)


def test_evidence_location_rejects_invalid_page_and_order():
    with pytest.raises(ValidationError):
        EvidenceLocation(page=0)

    with pytest.raises(ValidationError):
        EvidenceLocation(chunk_order=-1)


def test_complete_research_context_can_be_assembled():
    evidence = EvidenceRecord(
        evidence_id="E1",
        doc_id="doc-1",
        filename="financials.xlsx",
        chunk_id="doc-1::2",
        text="2023 revenue was $100 million.",
        query="2023 revenue",
        retrieval_score=0.91,
        location=EvidenceLocation(sheet="Revenue", chunk_order=2),
        requirement_ids=["R1"],
    )
    requirement = AnswerRequirement(
        requirement_id="R1",
        description="Find 2023 revenue",
        status=RequirementStatus.SUPPORTED,
        evidence_ids=["E1"],
    )
    claim = MaterialClaim(
        claim_id="C1",
        text="2023 revenue was $100 million.",
        evidence_ids=["E1"],
    )
    attempt = SearchAttempt(
        tool_name="search_evidence",
        query="2023 revenue",
        result_evidence_ids=["E1"],
        new_evidence_count=1,
        duration_ms=12,
    )

    context = ResearchContext(
        request_id="req-1",
        original_query="What was revenue in 2023?",
        resolved_query="What was Meridian's total revenue in 2023?",
        history=[ConversationTurn(role="user", content="Tell me about Meridian.")],
        authorized_doc_ids=["doc-1"],
        requirements=[requirement],
        evidence=[evidence],
        attempts=[attempt],
        claims=[claim],
        stop_reason=StopReason.COMPLETE,
    )

    assert context.requirements[0].evidence_ids == ["E1"]
    assert context.evidence[0].location.sheet == "Revenue"
    assert context.claims[0].evidence_ids == ["E1"]
    assert context.stop_reason is StopReason.COMPLETE
