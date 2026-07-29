"""Tests for the internal agentic-search state models."""
from datetime import timezone

import pytest
from pydantic import ValidationError

from app.models.research import (
    AgentAnswer,
    AgentAnswerOutcome,
    EvidenceDiscovery,
    EvidenceLocation,
    EvidenceRecord,
    ResearchContext,
    SearchAttempt,
)
from app.models.schemas import ConversationTurn


def test_agent_answer_has_only_answer_and_outcome() -> None:
    result = AgentAnswer(
        answer="The documents support this answer. [E1]",
        outcome=AgentAnswerOutcome.ANSWERED,
    )

    assert result.model_dump() == {
        "answer": "The documents support this answer. [E1]",
        "outcome": "answered",
    }


def test_research_context_defaults_are_isolated() -> None:
    first = ResearchContext(request_id="req-1", original_query="Question one")
    second = ResearchContext(request_id="req-2", original_query="Question two")

    first.evidence.append(
        EvidenceRecord(
            evidence_id="E1",
            doc_id="doc-1",
            filename="source.pdf",
            chunk_id="doc-1::0",
            text="Evidence.",
            discoveries=[EvidenceDiscovery(query="question one")],
        )
    )

    assert second.evidence == []
    assert first.started_at.tzinfo == timezone.utc


def test_research_context_rejects_non_positive_turn_limit() -> None:
    with pytest.raises(ValidationError):
        ResearchContext(
            request_id="req-1",
            original_query="Question",
            max_turns=0,
        )


def test_evidence_location_rejects_invalid_order() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocation(chunk_order=-1)


def test_runtime_research_context_can_be_assembled() -> None:
    evidence = EvidenceRecord(
        evidence_id="E1",
        doc_id="doc-1",
        filename="financials.xlsx",
        chunk_id="doc-1::2",
        text="2023 revenue was $100 million.",
        location=EvidenceLocation(chunk_order=2),
        discoveries=[EvidenceDiscovery(query="2023 revenue", retrieval_score=0.91)],
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
        history=[ConversationTurn(role="user", content="Tell me about Meridian.")],
        authorized_doc_ids=["doc-1"],
        evidence=[evidence],
        attempts=[attempt],
    )

    assert context.evidence[0].location.chunk_order == 2
    assert context.attempts[0].result_evidence_ids == ["E1"]
