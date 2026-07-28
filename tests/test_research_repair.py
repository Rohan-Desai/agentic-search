from types import SimpleNamespace

import pytest

from app.agents.research_agent import ResearchRunResult
from app.agents.research_repair import (
    build_repair_input,
    build_research_repair_agent,
    validate_and_repair_research,
)
from app.models.research import (
    AnswerRequirement,
    EvidenceAssessment,
    EvidenceDiscovery,
    EvidenceRecord,
    EvidenceRelationship,
    MaterialClaim,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchBudget,
    ResearchContext,
    ResearchOutcome,
    StopReason,
)


def evidence(evidence_id: str = "E1", *, doc_id: str = "doc-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        doc_id=doc_id,
        filename="policy.pdf",
        chunk_id=f"chunk-{evidence_id}",
        text="The policy limit is 30 days.",
        discoveries=[EvidenceDiscovery(query="policy limit")],
    )


def context(*, budget: ResearchBudget | None = None) -> ResearchContext:
    return ResearchContext(
        request_id="request-1",
        original_query="What is the policy limit?",
        authorized_doc_ids=["doc-1"],
        evidence=[evidence()],
        budget=budget or ResearchBudget(),
    )


def valid_output() -> ResearchAgentOutput:
    return ResearchAgentOutput(
        resolved_query="What is the policy limit?",
        outcome=ResearchOutcome.COMPLETE,
        answer="The policy limit is 30 days.",
        requirements=[
            AnswerRequirement(
                requirement_id="req-1",
                description="Identify the policy limit.",
                status=RequirementStatus.SUPPORTED,
                evidence_ids=["E1"],
            )
        ],
        evidence_assessments=[
            EvidenceAssessment(
                evidence_id="E1",
                requirement_id="req-1",
                relationship=EvidenceRelationship.SUPPORTS,
            )
        ],
        claims=[
            MaterialClaim(
                claim_id="claim-1",
                text="The policy limit is 30 days.",
                requirement_ids=["req-1"],
                evidence_ids=["E1"],
            )
        ],
        stop_reason=StopReason.COMPLETE,
    )


def invalid_output() -> ResearchAgentOutput:
    output = valid_output()
    output.claims[0].evidence_ids = ["E404"]
    return output


def research_run(
    output: ResearchAgentOutput,
    *,
    research_context: ResearchContext | None = None,
) -> ResearchRunResult:
    return ResearchRunResult(
        output=output,
        context=research_context or context(),
        new_items=("initial-item",),
    )


def test_repair_agent_is_structured_and_has_no_tools() -> None:
    agent = build_research_repair_agent(model="test-model")

    assert agent.model == "test-model"
    assert agent.output_type is ResearchAgentOutput
    assert agent.tools == []
    assert "This is a correction pass, not new research" in agent.instructions


def test_repair_input_contains_errors_proposal_and_bounded_evidence() -> None:
    run = research_run(invalid_output())
    from app.services.grounding_validator import validate_research_output

    validation = validate_research_output(run.context, run.output)
    repair_input = build_repair_input(run.context, run.output, validation)

    assert "claim claim-1 references unknown evidence: E404" in repair_input
    assert '"evidence_id": "E1"' in repair_input
    assert "The policy limit is 30 days." in repair_input
    assert '"E404"' in repair_input


@pytest.mark.asyncio
async def test_valid_output_skips_repair() -> None:
    called = False

    async def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    result = await validate_and_repair_research(
        research_run(valid_output()),
        run=fake_run,
    )

    assert result.validation.valid is True
    assert result.repair_attempted is False
    assert called is False
    assert result.context.usage.repair_attempts == 0


@pytest.mark.asyncio
async def test_repairable_output_gets_one_tool_free_repair_and_revalidation() -> None:
    captured = {}

    async def fake_run(agent, input, *, max_turns):
        captured.update(agent=agent, input=input, max_turns=max_turns)
        return SimpleNamespace(
            final_output=valid_output(),
            new_items=["repair-item"],
            raw_responses=[object()],
        )

    result = await validate_and_repair_research(
        research_run(invalid_output()),
        model="test-model",
        run=fake_run,
    )

    assert captured["max_turns"] == 1
    assert captured["agent"].tools == []
    assert result.initial_validation.valid is False
    assert result.validation.valid is True
    assert result.repair_attempted is True
    assert result.output == valid_output()
    assert result.context.claims == valid_output().claims
    assert result.context.validation is result.validation
    assert result.context.usage.repair_attempts == 1
    assert result.context.usage.turns == 1
    assert result.new_items == ("initial-item", "repair-item")


@pytest.mark.asyncio
async def test_failed_repair_is_returned_invalid_without_second_attempt() -> None:
    calls = 0

    async def fake_run(agent, input, *, max_turns):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            final_output=invalid_output(),
            new_items=[],
            raw_responses=[],
        )

    result = await validate_and_repair_research(
        research_run(invalid_output()),
        run=fake_run,
    )

    assert calls == 1
    assert result.repair_attempted is True
    assert result.validation.valid is False
    assert result.context.usage.repair_attempts == 1


@pytest.mark.asyncio
async def test_non_repairable_context_failure_skips_model_repair() -> None:
    called = False
    bad_context = context()
    bad_context.evidence[0].doc_id = "unauthorized"

    async def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    result = await validate_and_repair_research(
        research_run(valid_output(), research_context=bad_context),
        run=fake_run,
    )

    assert result.validation.valid is False
    assert result.validation.repair_allowed is False
    assert result.repair_attempted is False
    assert called is False


@pytest.mark.asyncio
async def test_repair_budget_can_disable_the_attempt() -> None:
    called = False
    no_repair_context = context(
        budget=ResearchBudget(max_repair_attempts=0)
    )

    async def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    result = await validate_and_repair_research(
        research_run(invalid_output(), research_context=no_repair_context),
        run=fake_run,
    )

    assert result.validation.valid is False
    assert result.repair_attempted is False
    assert called is False
