import pytest

from app.models.research import (
    AnswerRequirement,
    EvidenceAssessment,
    EvidenceDiscovery,
    EvidenceLocation,
    EvidenceRecord,
    EvidenceRelationship,
    MaterialClaim,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
    StopReason,
)
from app.models.schemas import SearchMode
from app.services.research_response_service import (
    UnpublishableResearchError,
    build_validated_search_response,
)


def evidence(
    evidence_id: str,
    *,
    text: str | None = None,
    scores: list[float | None] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        doc_id=f"doc-{evidence_id}",
        filename=f"{evidence_id}.pdf",
        chunk_id=f"chunk-{evidence_id}",
        text=text or f"Passage {evidence_id}.",
        location=EvidenceLocation(page=3, section="Limits"),
        discoveries=[
            EvidenceDiscovery(query=f"query-{index}", retrieval_score=score)
            for index, score in enumerate(scores or [0.7])
        ],
    )


def requirement(
    requirement_id: str,
    status: RequirementStatus,
    evidence_ids: list[str],
) -> AnswerRequirement:
    return AnswerRequirement(
        requirement_id=requirement_id,
        description=f"Answer {requirement_id}.",
        status=status,
        evidence_ids=evidence_ids,
    )


def assessment(
    evidence_id: str,
    requirement_id: str,
) -> EvidenceAssessment:
    return EvidenceAssessment(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        relationship=EvidenceRelationship.SUPPORTS,
    )


def claim(
    claim_id: str,
    requirement_id: str,
    evidence_ids: list[str],
) -> MaterialClaim:
    return MaterialClaim(
        claim_id=claim_id,
        text=f"Claim {claim_id}.",
        requirement_ids=[requirement_id],
        evidence_ids=evidence_ids,
    )


def complete_output() -> ResearchAgentOutput:
    return ResearchAgentOutput(
        resolved_query="What is the limit?",
        outcome=ResearchOutcome.COMPLETE,
        answer="The limit is 30 days.",
        requirements=[
            requirement("limit", RequirementStatus.SUPPORTED, ["E1"])
        ],
        evidence_assessments=[assessment("E1", "limit")],
        claims=[claim("limit-claim", "limit", ["E1"])],
        stop_reason=StopReason.COMPLETE,
    )


def context_with(*records: EvidenceRecord) -> ResearchContext:
    return ResearchContext(
        request_id="request-1",
        original_query="What is the limit?",
        evidence=list(records),
    )


def test_complete_response_cites_only_claim_used_evidence() -> None:
    used = evidence("E1", scores=[0.5, None, 0.9])
    unused = evidence("E2")
    response = build_validated_search_response(
        query="What is the limit?",
        output=complete_output(),
        context=context_with(used, unused),
    )

    assert response.mode is SearchMode.AGENTIC
    assert response.answer == "The limit is 30 days."
    assert response.answer_found is True
    assert response.clarification_needed is False
    assert response.partial is False
    assert len(response.citations) == 1
    assert response.citations[0].doc_id == "doc-E1"
    assert response.citations[0].score == 0.9
    assert response.citations[0].page == 3
    assert response.citations[0].section == "Limits"


def test_citations_are_deduplicated_in_claim_order_and_snippets_are_bounded() -> None:
    output = complete_output()
    output.requirements[0].evidence_ids.append("E2")
    output.evidence_assessments.append(assessment("E2", "limit"))
    output.claims = [
        claim("first", "limit", ["E2", "E1"]),
        claim("second", "limit", ["E1"]),
    ]

    response = build_validated_search_response(
        query="What is the limit?",
        output=output,
        context=context_with(evidence("E1"), evidence("E2", text="x" * 250)),
    )

    assert [item.chunk_id for item in response.citations] == [
        "chunk-E2",
        "chunk-E1",
    ]
    assert response.citations[0].snippet == "x" * 200


@pytest.mark.parametrize(
    ("outcome", "answer_found", "clarification_needed", "partial"),
    [
        (ResearchOutcome.PARTIAL, True, False, True),
        (ResearchOutcome.CLARIFICATION, False, True, False),
        (ResearchOutcome.NOT_FOUND, False, False, False),
    ],
)
def test_outcomes_map_to_safe_public_flags(
    outcome: ResearchOutcome,
    answer_found: bool,
    clarification_needed: bool,
    partial: bool,
) -> None:
    output = complete_output()
    output.outcome = outcome
    if outcome is ResearchOutcome.PARTIAL:
        output.requirements.append(
            requirement("missing", RequirementStatus.NOT_FOUND, [])
        )
        output.missing_requirements = ["missing"]
        output.stop_reason = StopReason.NO_PROGRESS
    elif outcome is ResearchOutcome.CLARIFICATION:
        output.claims = []
        output.requirements = []
        output.evidence_assessments = []
        output.stop_reason = StopReason.CLARIFICATION
    else:
        output.claims = []
        output.requirements = [
            requirement("limit", RequirementStatus.NOT_FOUND, [])
        ]
        output.evidence_assessments = []
        output.missing_requirements = ["limit"]
        output.stop_reason = StopReason.NOT_FOUND

    response = build_validated_search_response(
        query="Question",
        output=output,
        context=context_with(evidence("E1")),
    )

    assert response.answer_found is answer_found
    assert response.clarification_needed is clarification_needed
    assert response.partial is partial
    if not answer_found:
        assert response.citations == []


def test_invalid_research_output_cannot_be_projected() -> None:
    output = complete_output()
    output.claims[0].evidence_ids = ["E404"]

    with pytest.raises(
        UnpublishableResearchError,
        match="failed grounding validation",
    ):
        build_validated_search_response(
            query="Question",
            output=output,
            context=context_with(evidence("E1")),
        )


def test_projection_revalidates_against_the_current_context() -> None:
    with pytest.raises(
        UnpublishableResearchError,
        match="failed grounding validation",
    ):
        build_validated_search_response(
            query="Question",
            output=complete_output(),
            context=context_with(),
        )
