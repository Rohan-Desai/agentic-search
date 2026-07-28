"""Agent-driven document search using the OpenAI Agents SDK tool loop."""
from __future__ import annotations

import re
from uuid import uuid4

from agents import Agent, Runner, set_default_openai_key

from app.agents.base import default_model
from app.agents.research_tools import AGENTIC_RESEARCH_TOOLS, AgentToolContext
from app.core.config import get_settings
from app.models.research import (
    AgentAnswer,
    AgentAnswerOutcome,
    EvidenceRecord,
    ResearchContext,
    SearchAttempt,
)
from app.models.schemas import (
    AgentStep,
    Citation,
    ConversationTurn,
    SearchMode,
    SearchResponse,
)

_EVIDENCE_GROUP = re.compile(r"\[(E\d+(?:\s*,\s*E\d+)*)\]")
_EVIDENCE_ID = re.compile(r"E\d+")
_SNIPPET_CHARS = 200

AGENT_INSTRUCTIONS = """
Answer questions using only evidence returned by the document tools.

- Decide which searches to run and reformulate when results are weak or incomplete.
- Search separately for materially different parts of a multi-part question.
- Before answering a multi-part question, check that every requested part is
  addressed and search again for any missing part.
- If repeated searches return the same evidence, use list_documents to identify
  a likely source and search within that document by ID.
- In the final answer, explicitly address every requested part. If one part
  remains unsupported, say exactly which information was not found.
- For calculations and table comparisons, search for the underlying datasets
  and inputs rather than repeatedly searching for the requested calculation.
- Inspect nearby context when a passage may be missing a qualification.
- Cite supporting evidence IDs inline as [E1][E2] or [E1, E2].
- Never invent an evidence ID or use outside knowledge.
- Evidence IDs are valid only for the current request. Cite only IDs returned
  by tools during this run.
- For factual follow-up questions, use history to resolve the user's intent,
  then search again so the answer cites evidence from the current request.
- Never substitute general policy, assumptions, or speculation for missing
  question-specific evidence.
- If reasonable searches do not find the answer, return outcome "not_found".
- If ambiguity would materially change the answer, ask one focused question and
  return outcome "clarification".
- Otherwise return outcome "answered".
- Stop when the evidence supports the answer or further searching would repeat
  the same information.
""".strip()


def build_agent() -> Agent[AgentToolContext]:
    """Create the single agent used by agentic search."""

    return Agent[AgentToolContext](
        name="Agentic Search",
        model=default_model(),
        instructions=AGENT_INSTRUCTIONS,
        tools=AGENTIC_RESEARCH_TOOLS,
        output_type=AgentAnswer,
    )


def build_agent_input(
    query: str,
    history: list[ConversationTurn] | None,
) -> str:
    """Render history and the current question for multi-turn resolution."""

    lines = ["Conversation history:"]
    if history:
        lines.extend(
            f"{turn.role.upper()}: {_EVIDENCE_GROUP.sub('', turn.content)}"
            for turn in history
        )
    else:
        lines.append("(none)")
    lines.extend(["", "Current question:", query])
    return "\n".join(lines)


def cited_evidence_ids(answer: str) -> list[str]:
    """Return unique inline evidence references in answer order."""

    evidence_ids = [
        evidence_id
        for group in _EVIDENCE_GROUP.findall(answer)
        for evidence_id in _EVIDENCE_ID.findall(group)
    ]
    return list(dict.fromkeys(evidence_ids))


def build_citations(
    answer: str,
    tool_context: AgentToolContext,
) -> list[Citation]:
    """Resolve the answer's evidence references through the request ledger."""

    return [
        _citation_from_evidence(tool_context.ledger.get(evidence_id))
        for evidence_id in cited_evidence_ids(answer)
    ]


def _citation_from_evidence(evidence: EvidenceRecord) -> Citation:
    scores = [
        discovery.retrieval_score
        for discovery in evidence.discoveries
        if discovery.retrieval_score is not None
    ]
    return Citation(
        doc_id=evidence.doc_id,
        filename=evidence.filename,
        chunk_id=evidence.chunk_id,
        snippet=evidence.text[:_SNIPPET_CHARS],
        score=max(scores, default=None),
    )


def build_steps(context: ResearchContext) -> list[AgentStep]:
    """Expose concise application-observed tool activity."""

    return [_step_from_attempt(attempt) for attempt in context.attempts]


def _step_from_attempt(attempt: SearchAttempt) -> AgentStep:
    details = [f"status={attempt.status.value}"]
    if attempt.tool_name == "list_documents":
        if attempt.error_code:
            details.append(f"error={attempt.error_code}")
        return AgentStep(
            kind="tool",
            name=attempt.tool_name,
            detail="; ".join(details),
        )
    if attempt.query:
        details.append(f"query={attempt.query}")
    details.append(f"results={len(attempt.result_evidence_ids)}")
    details.append(f"new_evidence={attempt.new_evidence_count}")
    if attempt.error_code:
        details.append(f"error={attempt.error_code}")
    return AgentStep(
        kind="tool",
        name=attempt.tool_name,
        detail="; ".join(details),
    )


async def run_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
) -> SearchResponse:
    """Let one agent search until it is ready to answer."""

    settings = get_settings()
    set_default_openai_key(settings.openai_api_key, use_for_tracing=False)

    context = ResearchContext(
        request_id=uuid4().hex,
        original_query=query,
        history=list(history or []),
        authorized_doc_ids=doc_ids,
        retrieval_top_k=top_k,
    )
    tool_context = AgentToolContext.create(context)
    result = await Runner.run(
        build_agent(),
        build_agent_input(query, history),
        context=tool_context,
        max_turns=context.budget.max_turns,
    )
    output = AgentAnswer.model_validate(result.final_output)

    return SearchResponse(
        query=query,
        mode=SearchMode.AGENTIC,
        answer=output.answer,
        citations=build_citations(output.answer, tool_context),
        steps=build_steps(context),
        clarification_needed=output.outcome is AgentAnswerOutcome.CLARIFICATION,
        answer_found=output.outcome is AgentAnswerOutcome.ANSWERED,
    )
