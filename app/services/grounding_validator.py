"""Deterministic structural grounding checks for proposed research answers."""
from __future__ import annotations

from collections import Counter, defaultdict

from app.models.research import (
    EvidenceRelationship,
    EvidenceStatus,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
    StopReason,
    ValidationResult,
)

_PARTIAL_STOP_REASONS = {
    StopReason.NO_PROGRESS,
    StopReason.BUDGET_EXHAUSTED,
    StopReason.TIMEOUT,
}
_CLAIM_GROUNDING_RELATIONSHIPS = {
    EvidenceRelationship.SUPPORTS,
    EvidenceRelationship.QUALIFIES,
}


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def validate_research_output(
    context: ResearchContext,
    output: ResearchAgentOutput,
) -> ValidationResult:
    """Validate references, coverage, conflicts, and terminal-state coherence.

    These checks establish structural grounding. They deliberately do not
    claim to prove that evidence text semantically entails a claim.
    """

    errors: list[str] = []
    warnings: list[str] = []
    context_integrity_error = False

    evidence_ids = [item.evidence_id for item in context.evidence]
    evidence_by_id = {item.evidence_id: item for item in context.evidence}
    duplicate_evidence = _duplicates(evidence_ids)
    if duplicate_evidence:
        errors.append(
            f"context has duplicate evidence IDs: {', '.join(duplicate_evidence)}"
        )
        context_integrity_error = True

    source_keys = [f"{item.doc_id}/{item.chunk_id}" for item in context.evidence]
    duplicate_sources = _duplicates(source_keys)
    if duplicate_sources:
        errors.append(
            f"context has duplicate canonical sources: {', '.join(duplicate_sources)}"
        )
        context_integrity_error = True

    if context.authorized_doc_ids is not None:
        authorized = set(context.authorized_doc_ids)
        unauthorized = sorted(
            {
                item.doc_id
                for item in context.evidence
                if item.doc_id not in authorized
            }
        )
        if unauthorized:
            errors.append(
                f"context contains evidence from unauthorized documents: "
                f"{', '.join(unauthorized)}"
            )
            context_integrity_error = True

    requirement_ids = [item.requirement_id for item in output.requirements]
    requirement_by_id = {
        item.requirement_id: item for item in output.requirements
    }
    duplicate_requirements = _duplicates(requirement_ids)
    if duplicate_requirements:
        errors.append(
            f"duplicate requirement IDs: {', '.join(duplicate_requirements)}"
        )

    claim_ids = [item.claim_id for item in output.claims]
    duplicate_claims = _duplicates(claim_ids)
    if duplicate_claims:
        errors.append(f"duplicate claim IDs: {', '.join(duplicate_claims)}")

    assessment_keys = [
        f"{item.requirement_id}/{item.evidence_id}"
        for item in output.evidence_assessments
    ]
    duplicate_assessments = _duplicates(assessment_keys)
    if duplicate_assessments:
        errors.append(
            f"duplicate evidence assessments: {', '.join(duplicate_assessments)}"
        )

    assessments_by_requirement = defaultdict(list)
    assessment_by_pair = {}
    for assessment in output.evidence_assessments:
        if assessment.requirement_id not in requirement_by_id:
            errors.append(
                f"assessment references unknown requirement "
                f"{assessment.requirement_id}"
            )
        if assessment.evidence_id not in evidence_by_id:
            errors.append(
                f"assessment references unknown evidence {assessment.evidence_id}"
            )
        assessments_by_requirement[assessment.requirement_id].append(assessment)
        assessment_by_pair[
            (assessment.requirement_id, assessment.evidence_id)
        ] = assessment

    for requirement in output.requirements:
        unknown_evidence = sorted(
            set(requirement.evidence_ids) - set(evidence_by_id)
        )
        if unknown_evidence:
            errors.append(
                f"requirement {requirement.requirement_id} references unknown "
                f"evidence: {', '.join(unknown_evidence)}"
            )

        assessed_ids = {
            item.evidence_id
            for item in assessments_by_requirement[requirement.requirement_id]
        }
        listed_ids = set(requirement.evidence_ids)
        if listed_ids != assessed_ids:
            errors.append(
                f"requirement {requirement.requirement_id} evidence IDs do not "
                "match its assessments"
            )

        relationships = {
            item.relationship
            for item in assessments_by_requirement[requirement.requirement_id]
            if item.evidence_id in evidence_by_id
        }
        has_support = EvidenceRelationship.SUPPORTS in relationships
        has_contradiction = EvidenceRelationship.CONTRADICTS in relationships

        if requirement.status is RequirementStatus.SUPPORTED:
            if not has_support:
                errors.append(
                    f"supported requirement {requirement.requirement_id} has no "
                    "supporting assessment"
                )
            if has_contradiction:
                errors.append(
                    f"supported requirement {requirement.requirement_id} has "
                    "unresolved contradictory evidence"
                )
        elif requirement.status is RequirementStatus.CONFLICTING:
            if not has_support or not has_contradiction:
                errors.append(
                    f"conflicting requirement {requirement.requirement_id} needs "
                    "both supporting and contradictory assessments"
                )
        elif requirement.status in {
            RequirementStatus.UNSEARCHED,
            RequirementStatus.NOT_FOUND,
        } and (listed_ids or relationships):
            errors.append(
                f"{requirement.status.value} requirement "
                f"{requirement.requirement_id} cannot contain assessed evidence"
            )

    claims_by_requirement = defaultdict(list)
    claimed_relationships_by_requirement = defaultdict(set)
    for claim in output.claims:
        unknown_requirements = sorted(
            set(claim.requirement_ids) - set(requirement_by_id)
        )
        if unknown_requirements:
            errors.append(
                f"claim {claim.claim_id} references unknown requirements: "
                f"{', '.join(unknown_requirements)}"
            )

        unknown_evidence = sorted(set(claim.evidence_ids) - set(evidence_by_id))
        if unknown_evidence:
            errors.append(
                f"claim {claim.claim_id} references unknown evidence: "
                f"{', '.join(unknown_evidence)}"
            )

        for requirement_id in claim.requirement_ids:
            claims_by_requirement[requirement_id].append(claim)

        for evidence_id in claim.evidence_ids:
            matching_assessments = [
                assessment_by_pair.get((requirement_id, evidence_id))
                for requirement_id in claim.requirement_ids
            ]
            if not any(
                assessment is not None
                and (
                    assessment.relationship in _CLAIM_GROUNDING_RELATIONSHIPS
                    or (
                        assessment.relationship
                        is EvidenceRelationship.CONTRADICTS
                        and requirement_by_id.get(assessment.requirement_id)
                        is not None
                        and requirement_by_id[
                            assessment.requirement_id
                        ].status
                        is RequirementStatus.CONFLICTING
                    )
                )
                for assessment in matching_assessments
            ):
                errors.append(
                    f"claim {claim.claim_id} evidence {evidence_id} is not "
                    "grounded in a referenced requirement"
                )
            for assessment in matching_assessments:
                if assessment is not None:
                    claimed_relationships_by_requirement[
                        assessment.requirement_id
                    ].add(assessment.relationship)
            evidence = evidence_by_id.get(evidence_id)
            if evidence is not None and evidence.status is EvidenceStatus.REJECTED:
                errors.append(
                    f"claim {claim.claim_id} uses rejected evidence {evidence_id}"
                )
            elif evidence is not None and evidence.status is EvidenceStatus.WEAK:
                warnings.append(
                    f"claim {claim.claim_id} relies on weak evidence {evidence_id}"
                )

    for requirement in output.requirements:
        if (
            requirement.status is RequirementStatus.SUPPORTED
            and not claims_by_requirement[requirement.requirement_id]
        ):
            errors.append(
                f"supported requirement {requirement.requirement_id} has no "
                "material claim"
            )
        elif requirement.status is RequirementStatus.CONFLICTING:
            claimed_relationships = claimed_relationships_by_requirement[
                requirement.requirement_id
            ]
            if not {
                EvidenceRelationship.SUPPORTS,
                EvidenceRelationship.CONTRADICTS,
            } <= claimed_relationships:
                errors.append(
                    f"conflicting requirement {requirement.requirement_id} must "
                    "expose claims from both sides"
                )

    missing_ids = set(output.missing_requirements)
    conflict_ids = set(output.unresolved_conflicts)
    duplicate_missing = _duplicates(output.missing_requirements)
    duplicate_conflicts = _duplicates(output.unresolved_conflicts)
    if duplicate_missing:
        errors.append(
            f"duplicate missing requirement IDs: {', '.join(duplicate_missing)}"
        )
    if duplicate_conflicts:
        errors.append(
            f"duplicate unresolved conflict IDs: {', '.join(duplicate_conflicts)}"
        )
    unknown_missing = sorted(missing_ids - set(requirement_by_id))
    unknown_conflicts = sorted(conflict_ids - set(requirement_by_id))
    if unknown_missing:
        errors.append(
            f"missing_requirements contains unknown IDs: {', '.join(unknown_missing)}"
        )
    if unknown_conflicts:
        errors.append(
            f"unresolved_conflicts contains unknown IDs: "
            f"{', '.join(unknown_conflicts)}"
        )

    expected_missing = {
        item.requirement_id
        for item in output.requirements
        if item.status
        in {
            RequirementStatus.UNSEARCHED,
            RequirementStatus.WEAK,
            RequirementStatus.NOT_FOUND,
        }
    }
    expected_conflicts = {
        item.requirement_id
        for item in output.requirements
        if item.status is RequirementStatus.CONFLICTING
    }
    if missing_ids != expected_missing:
        errors.append(
            "missing_requirements must exactly list unsearched, weak, and "
            "not-found requirement IDs"
        )
    if conflict_ids != expected_conflicts:
        errors.append(
            "unresolved_conflicts must exactly list conflicting requirement IDs"
        )

    _validate_terminal_state(output, errors)

    result = ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        repair_allowed=bool(errors) and not context_integrity_error,
    )
    context.validation = result
    return result


def _validate_terminal_state(
    output: ResearchAgentOutput,
    errors: list[str],
) -> None:
    statuses = {item.status for item in output.requirements}

    expected_stop_reason = {
        ResearchOutcome.COMPLETE: StopReason.COMPLETE,
        ResearchOutcome.CLARIFICATION: StopReason.CLARIFICATION,
        ResearchOutcome.NOT_FOUND: StopReason.NOT_FOUND,
    }.get(output.outcome)
    if expected_stop_reason is not None and output.stop_reason is not expected_stop_reason:
        errors.append(
            f"{output.outcome.value} outcome requires "
            f"{expected_stop_reason.value} stop reason"
        )

    if output.outcome is ResearchOutcome.COMPLETE:
        if not output.requirements:
            errors.append("complete outcome requires at least one requirement")
        if statuses - {RequirementStatus.SUPPORTED}:
            errors.append("complete outcome requires every requirement to be supported")
    elif output.outcome is ResearchOutcome.PARTIAL:
        if output.stop_reason not in _PARTIAL_STOP_REASONS:
            errors.append(
                "partial outcome requires no_progress, budget_exhausted, or "
                "timeout stop reason"
            )
        if not output.claims:
            errors.append("partial outcome requires at least one grounded claim")
        if statuses and statuses <= {RequirementStatus.SUPPORTED}:
            errors.append("partial outcome requires missing or conflicting coverage")
    elif output.outcome is ResearchOutcome.CLARIFICATION:
        if output.claims:
            errors.append("clarification outcome cannot include material claims")
    elif output.outcome is ResearchOutcome.NOT_FOUND:
        if not output.requirements:
            errors.append("not_found outcome requires at least one requirement")
        if output.claims:
            errors.append("not_found outcome cannot include material claims")
        if RequirementStatus.SUPPORTED in statuses:
            errors.append("not_found outcome cannot contain supported requirements")
        if RequirementStatus.CONFLICTING in statuses:
            errors.append("not_found outcome cannot contain conflicting requirements")
