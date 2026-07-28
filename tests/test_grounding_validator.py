from app.models.research import (
    AnswerRequirement,
    ClaimType,
    EvidenceAssessment,
    EvidenceDiscovery,
    EvidenceRecord,
    EvidenceRelationship,
    EvidenceStatus,
    MaterialClaim,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
    StopReason,
)
from app.services.grounding_validator import validate_research_output


def evidence(
    evidence_id: str,
    *,
    doc_id: str = "doc-1",
    status: EvidenceStatus = EvidenceStatus.DIRECT,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        doc_id=doc_id,
        filename=f"{doc_id}.pdf",
        chunk_id=f"chunk-{evidence_id}",
        text=f"Passage for {evidence_id}.",
        status=status,
        discoveries=[EvidenceDiscovery(query="policy limit")],
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
    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
) -> EvidenceAssessment:
    return EvidenceAssessment(
        evidence_id=evidence_id,
        requirement_id=requirement_id,
        relationship=relationship,
    )


def claim(
    claim_id: str,
    requirement_ids: list[str],
    evidence_ids: list[str],
) -> MaterialClaim:
    return MaterialClaim(
        claim_id=claim_id,
        text=f"Claim {claim_id}.",
        requirement_ids=requirement_ids,
        evidence_ids=evidence_ids,
        claim_type=ClaimType.DIRECT,
    )


def context_with(*records: EvidenceRecord) -> ResearchContext:
    return ResearchContext(
        request_id="request-1",
        original_query="What is the policy?",
        authorized_doc_ids=["doc-1"],
        evidence=list(records),
    )


def complete_output() -> ResearchAgentOutput:
    return ResearchAgentOutput(
        resolved_query="What is the policy limit?",
        outcome=ResearchOutcome.COMPLETE,
        answer="The policy limit is 30 days.",
        requirements=[
            requirement("req-1", RequirementStatus.SUPPORTED, ["E1"])
        ],
        evidence_assessments=[assessment("E1", "req-1")],
        claims=[claim("claim-1", ["req-1"], ["E1"])],
        stop_reason=StopReason.COMPLETE,
    )


def test_valid_complete_output_passes_and_is_recorded_on_context() -> None:
    context = context_with(evidence("E1"))

    result = validate_research_output(context, complete_output())

    assert result.valid is True
    assert result.errors == []
    assert result.repair_allowed is False
    assert context.validation is result


def test_unknown_references_and_ungrounded_claim_fail_validation() -> None:
    context = context_with(evidence("E1"))
    output = complete_output()
    output.claims[0].evidence_ids = ["E404"]

    result = validate_research_output(context, output)

    assert result.valid is False
    assert "claim claim-1 references unknown evidence: E404" in result.errors
    assert (
        "claim claim-1 evidence E404 is not grounded in a referenced requirement"
        in result.errors
    )
    assert result.repair_allowed is True


def test_supported_requirement_requires_supporting_assessment_and_claim() -> None:
    context = context_with(evidence("E1"))
    output = complete_output()
    output.evidence_assessments = [
        assessment("E1", "req-1", EvidenceRelationship.CONTEXT)
    ]
    output.claims = []

    result = validate_research_output(context, output)

    assert (
        "supported requirement req-1 has no supporting assessment"
        in result.errors
    )
    assert "supported requirement req-1 has no material claim" in result.errors


def test_complete_output_cannot_hide_contradictory_evidence() -> None:
    context = context_with(evidence("E1"), evidence("E2"))
    output = complete_output()
    output.requirements[0].evidence_ids.append("E2")
    output.evidence_assessments.append(
        assessment("E2", "req-1", EvidenceRelationship.CONTRADICTS)
    )

    result = validate_research_output(context, output)

    assert (
        "supported requirement req-1 has unresolved contradictory evidence"
        in result.errors
    )


def test_valid_partial_output_discloses_missing_and_conflicting_requirements() -> None:
    context = context_with(evidence("E1"), evidence("E2"), evidence("E3"))
    output = ResearchAgentOutput(
        resolved_query="Compare both policies.",
        outcome=ResearchOutcome.PARTIAL,
        answer="The duration is known, but the eligibility sources conflict.",
        requirements=[
            requirement("duration", RequirementStatus.SUPPORTED, ["E1"]),
            requirement("eligibility", RequirementStatus.CONFLICTING, ["E2", "E3"]),
            requirement("exceptions", RequirementStatus.NOT_FOUND, []),
        ],
        evidence_assessments=[
            assessment("E1", "duration"),
            assessment("E2", "eligibility"),
            assessment(
                "E3",
                "eligibility",
                EvidenceRelationship.CONTRADICTS,
            ),
        ],
        claims=[claim("duration-claim", ["duration"], ["E1"])],
        missing_requirements=["exceptions"],
        unresolved_conflicts=["eligibility"],
        stop_reason=StopReason.NO_PROGRESS,
    )

    result = validate_research_output(context, output)

    assert result.valid is True


def test_conflicts_and_missing_coverage_must_be_disclosed_exactly() -> None:
    context = context_with(evidence("E1"), evidence("E2"))
    output = ResearchAgentOutput(
        resolved_query="Compare policies.",
        outcome=ResearchOutcome.PARTIAL,
        answer="The sources conflict.",
        requirements=[
            requirement("known", RequirementStatus.SUPPORTED, ["E1"]),
            requirement("conflict", RequirementStatus.CONFLICTING, ["E1", "E2"]),
            requirement("missing", RequirementStatus.WEAK, []),
        ],
        evidence_assessments=[
            assessment("E1", "known"),
            assessment("E1", "conflict"),
            assessment("E2", "conflict", EvidenceRelationship.CONTRADICTS),
        ],
        claims=[claim("claim-1", ["known"], ["E1"])],
        stop_reason=StopReason.NO_PROGRESS,
    )

    result = validate_research_output(context, output)

    assert (
        "missing_requirements must exactly list unsearched, weak, and "
        "not-found requirement IDs"
        in result.errors
    )
    assert (
        "unresolved_conflicts must exactly list conflicting requirement IDs"
        in result.errors
    )


def test_outcome_and_stop_reason_must_agree() -> None:
    context = context_with(evidence("E1"))
    output = complete_output()
    output.stop_reason = StopReason.BUDGET_EXHAUSTED

    result = validate_research_output(context, output)

    assert "complete outcome requires complete stop reason" in result.errors


def test_not_found_is_valid_without_claims_or_evidence() -> None:
    context = context_with()
    output = ResearchAgentOutput(
        resolved_query="What is the retention period?",
        outcome=ResearchOutcome.NOT_FOUND,
        answer="The documents do not state a retention period.",
        requirements=[
            requirement("retention", RequirementStatus.NOT_FOUND, [])
        ],
        missing_requirements=["retention"],
        stop_reason=StopReason.NOT_FOUND,
    )

    result = validate_research_output(context, output)

    assert result.valid is True


def test_not_found_requires_a_tracked_requirement() -> None:
    context = context_with()
    output = ResearchAgentOutput(
        resolved_query="What is the retention period?",
        outcome=ResearchOutcome.NOT_FOUND,
        answer="The documents do not state a retention period.",
        stop_reason=StopReason.NOT_FOUND,
    )

    result = validate_research_output(context, output)

    assert "not_found outcome requires at least one requirement" in result.errors


def test_context_scope_violation_is_not_model_repairable() -> None:
    context = context_with(evidence("E1", doc_id="unauthorized-doc"))

    result = validate_research_output(context, complete_output())

    assert (
        "context contains evidence from unauthorized documents: unauthorized-doc"
        in result.errors
    )
    assert result.repair_allowed is False


def test_rejected_evidence_cannot_ground_a_claim_and_weak_evidence_warns() -> None:
    rejected_context = context_with(
        evidence("E1", status=EvidenceStatus.REJECTED)
    )
    rejected = validate_research_output(rejected_context, complete_output())
    assert "claim claim-1 uses rejected evidence E1" in rejected.errors

    weak_context = context_with(evidence("E1", status=EvidenceStatus.WEAK))
    weak = validate_research_output(weak_context, complete_output())
    assert weak.valid is True
    assert weak.warnings == ["claim claim-1 relies on weak evidence E1"]
