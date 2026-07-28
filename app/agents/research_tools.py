"""Request-scoped OpenAI Agents SDK tools for document research."""
from __future__ import annotations

from dataclasses import dataclass

from agents import RunContextWrapper, function_tool

from app.agents.evidence_ledger import EvidenceLedger
from app.models.research import AttemptStatus, EvidenceSearchResult, ResearchContext
from app.services.retrieval_service import (
    RetrievalExecutionError,
    SearchStore,
    execute_evidence_search,
)


@dataclass
class AgentToolContext:
    """Private application state available to tools during one agent run."""

    research: ResearchContext
    ledger: EvidenceLedger
    store: SearchStore | None = None

    def __post_init__(self) -> None:
        if self.ledger.context is not self.research:
            raise ValueError("The evidence ledger must belong to the same research context.")

    @classmethod
    def create(
        cls,
        research: ResearchContext,
        *,
        store: SearchStore | None = None,
    ) -> AgentToolContext:
        """Create a tool context and ledger for one research request."""

        return cls(
            research=research,
            ledger=EvidenceLedger(research),
            store=store,
        )


def run_search_evidence(
    tool_context: AgentToolContext,
    *,
    query: str,
    doc_ids: list[str] | None = None,
    top_k: int = 5,
) -> EvidenceSearchResult:
    """Execute the model-facing search action as ordinary application code."""

    try:
        return execute_evidence_search(
            context=tool_context.research,
            ledger=tool_context.ledger,
            query=query,
            requested_doc_ids=doc_ids,
            top_k=top_k,
            store=tool_context.store,
        )
    except RetrievalExecutionError:
        attempt = tool_context.research.attempts[-1]
        return EvidenceSearchResult(
            status=AttemptStatus.FAILED,
            query=query,
            effective_doc_ids=attempt.effective_doc_ids,
            error_code=attempt.error_code,
        )


@function_tool
def search_evidence(
    wrapper: RunContextWrapper[AgentToolContext],
    query: str,
    doc_ids: list[str] | None = None,
    top_k: int = 5,
) -> str:
    """Find candidate evidence in the authorized document collection.

    Use this for an initial document search or a targeted follow-up. Results
    include stable evidence IDs, source passages, similarity scores, and
    whether each passage is new to this research run. Treat results as
    candidate evidence that still needs to be evaluated.

    Args:
        query: Focused natural-language search query.
        doc_ids: Optional document IDs to narrow the authorized search scope.
        top_k: Requested number of passages; the application enforces safe limits.
    """

    result = run_search_evidence(
        wrapper.context,
        query=query,
        doc_ids=doc_ids,
        top_k=top_k,
    )
    return result.model_dump_json()


AGENTIC_RESEARCH_TOOLS = [search_evidence]
