"""Focused tests for the minimal agentic-search integration."""
from types import SimpleNamespace

import pytest

from app.agents import agentic_search
from app.models.research import (
    AgentAnswer,
    AgentAnswerOutcome,
    AttemptStatus,
    EvidenceCandidate,
    SearchAttempt,
)
from app.models.schemas import ConversationTurn, SearchMode


@pytest.mark.asyncio
async def test_agent_runs_with_tools_history_scope_and_turn_limit(monkeypatch) -> None:
    captured = {}

    async def fake_run(agent, prompt, **kwargs):
        captured.update(agent=agent, prompt=prompt, kwargs=kwargs)
        return SimpleNamespace(
            final_output=AgentAnswer(
                answer="Coral Bay has the higher price.",
                outcome=AgentAnswerOutcome.ANSWERED,
            ),
            new_items=[],
        )

    monkeypatch.setattr(agentic_search.Runner, "run", fake_run)

    response = await agentic_search.run_agentic_search(
        "Which one has the higher price?",
        top_k=5,
        doc_ids=["doc-1"],
        history=[
            ConversationTurn(
                role="user",
                content="Compare Redhawk and Coral Bay.",
            )
        ],
    )

    assert captured["agent"].tools == agentic_search.AGENTIC_RESEARCH_TOOLS
    assert "Compare Redhawk and Coral Bay." in captured["prompt"]
    assert "Which one has the higher price?" in captured["prompt"]
    assert captured["kwargs"]["context"].research.authorized_doc_ids == ["doc-1"]
    assert captured["kwargs"]["max_turns"] == 8
    assert response.mode is SearchMode.AGENTIC
    assert response.answer_found is True
    assert response.clarification_needed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "answer_found", "clarification_needed"),
    [
        (AgentAnswerOutcome.NOT_FOUND, False, False),
        (AgentAnswerOutcome.CLARIFICATION, False, True),
    ],
)
async def test_agent_outcome_sets_public_flags(
    monkeypatch,
    outcome,
    answer_found,
    clarification_needed,
) -> None:
    async def fake_run(*args, **kwargs):
        return SimpleNamespace(
            final_output=AgentAnswer(answer="A concise response.", outcome=outcome),
            new_items=[],
        )

    monkeypatch.setattr(agentic_search.Runner, "run", fake_run)

    response = await agentic_search.run_agentic_search(
        "Question",
        top_k=5,
        doc_ids=None,
    )

    assert response.answer_found is answer_found
    assert response.clarification_needed is clarification_needed


@pytest.mark.asyncio
async def test_cited_ledger_evidence_becomes_citation(monkeypatch) -> None:
    async def fake_run(*args, **kwargs):
        tool_context = kwargs["context"]
        tool_context.ledger.add(
            EvidenceCandidate(
                doc_id="doc-1",
                filename="policy.pdf",
                chunk_id="chunk-1",
                text="The COO has executive accountability for safety.",
                query="executive safety accountability",
                retrieval_score=0.82,
            )
        )
        tool_context.research.attempts.append(
            SearchAttempt(
                tool_name="search_evidence",
                query="executive safety accountability",
                result_evidence_ids=["E1"],
                new_evidence_count=1,
                status=AttemptStatus.SUCCEEDED,
            )
        )
        return SimpleNamespace(
            final_output=AgentAnswer(
                answer="The COO has executive accountability for safety. [E1]",
                outcome=AgentAnswerOutcome.ANSWERED,
            ),
            new_items=[],
        )

    monkeypatch.setattr(agentic_search.Runner, "run", fake_run)

    response = await agentic_search.run_agentic_search(
        "Who has executive accountability for safety?",
        top_k=5,
        doc_ids=None,
    )

    assert len(response.citations) == 1
    assert response.citations[0].filename == "policy.pdf"
    assert response.citations[0].score == 0.82
    assert [step.model_dump() for step in response.steps] == [
        {
            "kind": "tool",
            "name": "search_evidence",
            "detail": (
                "status=succeeded; query=executive safety accountability; "
                "results=1; new_evidence=1"
            ),
        }
    ]


def test_cited_evidence_ids_are_ordered_and_deduplicated() -> None:
    assert agentic_search.cited_evidence_ids(
        "First [E2], then [E1], then [E2] again."
    ) == ["E2", "E1"]
