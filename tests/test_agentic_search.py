import asyncio

import pytest
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError

from app.agents.agentic_search import (
    AgenticSearchRuntimeError,
    execute_agentic_search,
)
from app.agents.research_agent import ResearchRunResult
from app.agents.research_repair import ValidatedResearchRunResult
from app.models.research import (
    AnswerRequirement,
    AttemptStatus,
    EvidenceAssessment,
    EvidenceDiscovery,
    EvidenceRecord,
    EvidenceRelationship,
    MaterialClaim,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
    SearchAttempt,
    StopReason,
    ValidationResult,
)
from app.models.schemas import ConversationTurn, SearchMode


def completed_state() -> tuple[ResearchContext, ResearchAgentOutput]:
    evidence = EvidenceRecord(
        evidence_id="E1",
        doc_id="doc-1",
        filename="policy.pdf",
        chunk_id="chunk-1",
        text="The policy limit is 30 days.",
        discoveries=[EvidenceDiscovery(query="policy limit", retrieval_score=0.9)],
    )
    requirement = AnswerRequirement(
        requirement_id="limit",
        description="Identify the policy limit.",
        status=RequirementStatus.SUPPORTED,
        evidence_ids=["E1"],
    )
    output = ResearchAgentOutput(
        resolved_query="What is the policy limit?",
        outcome=ResearchOutcome.COMPLETE,
        answer="The policy limit is 30 days.",
        requirements=[requirement],
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id="E1",
                requirement_id="limit",
                relationship=EvidenceRelationship.SUPPORTS,
            )
        ],
        claims=[
            MaterialClaim(
                claim_id="limit-claim",
                text="The policy limit is 30 days.",
                requirement_ids=["limit"],
                evidence_ids=["E1"],
            )
        ],
        stop_reason=StopReason.COMPLETE,
    )
    context = ResearchContext(
        request_id="request-1",
        original_query="What is the policy limit?",
        authorized_doc_ids=["doc-1"],
        requirements=output.requirements,
        evidence=[evidence],
        evidence_assessments=output.evidence_assessments,
        claims=output.claims,
        attempts=[
            SearchAttempt(
                tool_name="search_evidence",
                query="policy limit",
                effective_doc_ids=["doc-1"],
                result_evidence_ids=["E1"],
                new_evidence_count=1,
                duration_ms=12,
                status=AttemptStatus.SUCCEEDED,
            )
        ],
        stop_reason=StopReason.COMPLETE,
    )
    return context, output


async def test_pipeline_forwards_request_and_projects_validated_result() -> None:
    captured = {}
    context, output = completed_state()
    initial = ResearchRunResult(output=output, context=context, new_items=())
    validated = ValidatedResearchRunResult(
        output=output,
        context=context,
        validation=ValidationResult(valid=True),
        initial_validation=ValidationResult(valid=True),
        repair_attempted=False,
        new_items=(),
    )
    history = [ConversationTurn(role="user", content="Tell me about the policy.")]

    async def fake_research(query, **kwargs):
        captured.update(query=query, **kwargs)
        return initial

    async def fake_validate_and_repair(result):
        assert result is initial
        return validated

    response = await execute_agentic_search(
        "What is its limit?",
        top_k=7,
        doc_ids=["doc-1"],
        history=history,
        research=fake_research,
        validate_and_repair=fake_validate_and_repair,
    )

    assert captured == {
        "query": "What is its limit?",
        "top_k": 7,
        "doc_ids": ["doc-1"],
        "history": history,
    }
    assert response.mode is SearchMode.AGENTIC
    assert response.answer == output.answer
    assert [item.chunk_id for item in response.citations] == ["chunk-1"]
    assert response.answer_found is True
    assert response.steps[0].kind == "tool"
    assert response.steps[0].name == "search_evidence"
    assert response.steps[0].detail == (
        "status=succeeded; query=policy limit; results=1; "
        "new_evidence=1; duration_ms=12"
    )
    assert response.steps[-1].detail == (
        "stop=complete; requirements_supported=1/1; "
        "evidence=1; repair=no"
    )


async def test_pipeline_reports_repair_in_operational_trace() -> None:
    context, output = completed_state()
    initial = ResearchRunResult(output=output, context=context, new_items=())

    async def fake_research(query, **kwargs):
        return initial

    async def fake_validate_and_repair(result):
        return ValidatedResearchRunResult(
            output=output,
            context=context,
            validation=ValidationResult(valid=True),
            initial_validation=ValidationResult(
                valid=False,
                errors=["repair me"],
                repair_allowed=True,
            ),
            repair_attempted=True,
            new_items=(),
        )

    response = await execute_agentic_search(
        "Question",
        top_k=5,
        doc_ids=None,
        research=fake_research,
        validate_and_repair=fake_validate_and_repair,
    )

    assert response.steps[-1].detail.endswith("repair=yes")


@pytest.mark.parametrize(
    ("exception", "code", "status_code"),
    [
        (MaxTurnsExceeded("too many turns"), "turn_budget_exhausted", 503),
        (ModelBehaviorError("bad model output"), "model_provider_failed", 502),
    ],
)
async def test_sdk_failures_are_translated_without_private_details(
    exception: Exception,
    code: str,
    status_code: int,
) -> None:
    async def failing_research(query, **kwargs):
        raise exception

    with pytest.raises(AgenticSearchRuntimeError) as caught:
        await execute_agentic_search(
            "Question",
            top_k=5,
            doc_ids=None,
            research=failing_research,
        )

    assert caught.value.code == code
    assert caught.value.status_code == status_code
    assert str(exception) not in caught.value.public_message


async def test_wall_clock_timeout_is_translated() -> None:
    async def slow_research(query, **kwargs):
        await asyncio.sleep(0.05)

    with pytest.raises(AgenticSearchRuntimeError) as caught:
        await execute_agentic_search(
            "Question",
            top_k=5,
            doc_ids=None,
            research=slow_research,
            timeout_seconds=0.001,
        )

    assert caught.value.code == "research_timeout"
    assert caught.value.status_code == 504


async def test_invalid_after_repair_is_never_published() -> None:
    context, output = completed_state()
    initial = ResearchRunResult(output=output, context=context, new_items=())

    async def fake_research(query, **kwargs):
        return initial

    async def invalid_repair(result):
        return ValidatedResearchRunResult(
            output=output,
            context=context,
            validation=ValidationResult(valid=False, errors=["still invalid"]),
            initial_validation=ValidationResult(valid=False),
            repair_attempted=True,
            new_items=(),
        )

    with pytest.raises(AgenticSearchRuntimeError) as caught:
        await execute_agentic_search(
            "Question",
            top_k=5,
            doc_ids=None,
            research=fake_research,
            validate_and_repair=invalid_repair,
        )

    assert caught.value.code == "invalid_research_output"


async def test_failed_retrieval_is_not_reported_as_no_answer() -> None:
    context, output = completed_state()
    context.attempts[0].status = AttemptStatus.FAILED
    initial = ResearchRunResult(output=output, context=context, new_items=())

    async def fake_research(query, **kwargs):
        return initial

    async def invalid_repair(result):
        return ValidatedResearchRunResult(
            output=output,
            context=context,
            validation=ValidationResult(valid=False, errors=["tool failed"]),
            initial_validation=ValidationResult(valid=False),
            repair_attempted=False,
            new_items=(),
        )

    with pytest.raises(AgenticSearchRuntimeError) as caught:
        await execute_agentic_search(
            "Question",
            top_k=5,
            doc_ids=None,
            research=fake_research,
            validate_and_repair=invalid_repair,
        )

    assert caught.value.code == "retrieval_failed"
