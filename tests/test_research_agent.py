from types import SimpleNamespace

import pytest

from app.agents.research_agent import (
    build_research_agent,
    build_research_input,
    run_structured_research,
)
from app.models.research import (
    AnswerRequirement,
    ClaimType,
    MaterialClaim,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchBudget,
    ResearchOutcome,
    StopReason,
)
from app.models.schemas import ConversationTurn


def complete_output() -> ResearchAgentOutput:
    requirement = AnswerRequirement(
        requirement_id="req-1",
        description="Identify the policy limit.",
        status=RequirementStatus.SUPPORTED,
        evidence_ids=["ev-1"],
    )
    claim = MaterialClaim(
        claim_id="claim-1",
        text="The policy limit is 30 days.",
        requirement_ids=["req-1"],
        evidence_ids=["ev-1"],
        claim_type=ClaimType.DIRECT,
    )
    return ResearchAgentOutput(
        resolved_query="What is the policy limit?",
        outcome=ResearchOutcome.COMPLETE,
        answer="The policy limit is 30 days.",
        requirements=[requirement],
        claims=[claim],
        stop_reason=StopReason.COMPLETE,
    )


def test_build_research_agent_exposes_only_bounded_research_tools() -> None:
    agent = build_research_agent(model="test-model")

    assert agent.model == "test-model"
    assert agent.output_type is ResearchAgentOutput
    assert [tool.name for tool in agent.tools] == [
        "search_evidence",
        "inspect_evidence_context",
        "list_documents",
    ]
    assert "untrusted data" in agent.instructions
    assert "Every material factual claim" in agent.instructions


def test_build_research_input_keeps_history_separate_from_current_question() -> None:
    rendered = build_research_input(
        "What about its limit?",
        [
            ConversationTurn(role="user", content="Explain the leave policy."),
            ConversationTurn(role="assistant", content="Which part?"),
        ],
    )

    assert rendered == (
        "Conversation history (oldest first; may be empty):\n"
        "USER: Explain the leave policy.\n"
        "ASSISTANT: Which part?\n\n"
        "Current question:\n"
        "What about its limit?"
    )


@pytest.mark.asyncio
async def test_run_structured_research_is_bounded_and_updates_request_state() -> None:
    captured: dict[str, object] = {}
    output = complete_output()

    async def fake_run(agent, input, *, context, max_turns):
        captured.update(
            agent=agent,
            input=input,
            tool_context=context,
            max_turns=max_turns,
        )
        return SimpleNamespace(
            final_output=output,
            new_items=["tool-item"],
            raw_responses=[object(), object()],
        )

    result = await run_structured_research(
        "What is the limit?",
        doc_ids=["doc-1"],
        budget=ResearchBudget(max_turns=3),
        model="test-model",
        request_id="request-1",
        run=fake_run,
    )

    assert captured["max_turns"] == 3
    assert captured["tool_context"].research is result.context
    assert captured["tool_context"].ledger.context is result.context
    assert result.output is output
    assert result.context.request_id == "request-1"
    assert result.context.authorized_doc_ids == ["doc-1"]
    assert result.context.resolved_query == output.resolved_query
    assert result.context.requirements == output.requirements
    assert result.context.claims == output.claims
    assert result.context.stop_reason is StopReason.COMPLETE
    assert result.context.usage.turns == 2
    assert result.new_items == ("tool-item",)


@pytest.mark.asyncio
async def test_each_research_run_receives_isolated_mutable_state() -> None:
    contexts = []

    async def fake_run(agent, input, *, context, max_turns):
        contexts.append(context)
        return SimpleNamespace(
            final_output=complete_output().model_dump(),
            new_items=[],
            raw_responses=[],
        )

    first = await run_structured_research("First?", run=fake_run)
    second = await run_structured_research("Second?", run=fake_run)

    assert first.context is not second.context
    assert contexts[0].ledger is not contexts[1].ledger
    assert first.context.request_id != second.context.request_id
