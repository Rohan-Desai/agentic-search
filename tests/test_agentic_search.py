"""Focused tests for the minimal agentic-search integration."""
from types import SimpleNamespace

import pytest

from app.agents import agentic_search
from app.models.research import AgentAnswer, AgentAnswerOutcome
from app.models.schemas import ConversationTurn, SearchMode


@pytest.mark.asyncio
async def test_agent_runs_with_tools_history_scope_and_turn_limit(monkeypatch) -> None:
    captured = {}

    async def fake_run(agent, prompt, **kwargs):
        captured.update(agent=agent, prompt=prompt, kwargs=kwargs)
        return SimpleNamespace(
            final_output=AgentAnswer(
                answer="Coral Bay has the higher price. [E1]",
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
