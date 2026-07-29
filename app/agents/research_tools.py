"""Request-scoped OpenAI Agents SDK tools for document research."""
from __future__ import annotations

from dataclasses import dataclass

from agents import RunContextWrapper, function_tool

from app.agents.evidence_ledger import EvidenceLedger
from app.models.research import (
    AttemptStatus,
    ContextInspectionResult,
    DocumentListResult,
    EvidenceSearchResult,
    ResearchContext,
)
from app.services.document_catalog_service import (
    DocumentCatalogError,
    execute_document_list,
)
from app.services.retrieval_service import (
    RetrievalExecutionError,
    SearchStore,
    execute_context_inspection,
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


def run_inspect_evidence_context(
    tool_context: AgentToolContext,
    *,
    evidence_id: str,
    before: int = 1,
    after: int = 1,
) -> ContextInspectionResult:
    """Execute bounded context inspection as ordinary application code."""

    try:
        return execute_context_inspection(
            context=tool_context.research,
            ledger=tool_context.ledger,
            evidence_id=evidence_id,
            before=before,
            after=after,
            store=tool_context.store,
        )
    except RetrievalExecutionError:
        attempt = tool_context.research.attempts[-1]
        return ContextInspectionResult(
            status=AttemptStatus.FAILED,
            source_evidence_id=evidence_id,
            error_code=attempt.error_code,
        )


def run_list_documents(tool_context: AgentToolContext) -> DocumentListResult:
    """Execute corpus discovery as ordinary application code."""

    try:
        return execute_document_list(
            context=tool_context.research,
            store=tool_context.store,
        )
    except DocumentCatalogError:
        return DocumentListResult(
            status=AttemptStatus.FAILED,
            error_code="document_catalog_failed",
        )


@function_tool
def search_evidence(
    wrapper: RunContextWrapper[AgentToolContext],
    query: str,
    doc_ids: list[str] | None = None,
) -> str:
    """Find candidate evidence in the authorized document collection.

    Use this for an initial document search or a targeted follow-up. Results
    include stable evidence IDs, source passages, hybrid rank scores, and
    whether each passage is new to this research run. Treat results as
    candidate evidence that still needs to be evaluated.

    Args:
        query: Focused natural-language search query.
        doc_ids: Optional document IDs to narrow the authorized search scope.
    """

    result = run_search_evidence(
        wrapper.context,
        query=query,
        doc_ids=doc_ids,
        top_k=wrapper.context.research.retrieval_top_k,
    )
    return result.model_dump_json()


@function_tool
def inspect_evidence_context(
    wrapper: RunContextWrapper[AgentToolContext],
    evidence_id: str,
    before: int = 1,
    after: int = 1,
) -> str:
    """Inspect a small window of chunks around already retrieved evidence.

    Use this when an isolated passage needs headings, caveats, definitions, or
    adjacent table context. The application limits the window and keeps the
    inspection inside the evidence's authorized source document.

    Args:
        evidence_id: Stable evidence ID returned by search_evidence.
        before: Requested chunks before the source passage (0-2).
        after: Requested chunks after the source passage (0-2).
    """

    result = run_inspect_evidence_context(
        wrapper.context,
        evidence_id=evidence_id,
        before=before,
        after=after,
    )
    return result.model_dump_json()


@function_tool
def list_documents(wrapper: RunContextWrapper[AgentToolContext]) -> str:
    """List documents available within the current authorized search scope.

    Use this to discover filenames and document IDs before a document-specific
    search or comparison. Catalog entries describe corpus scope; they are not
    evidence for claims about document contents.
    """

    return run_list_documents(wrapper.context).model_dump_json()


AGENTIC_RESEARCH_TOOLS = [
    search_evidence,
    inspect_evidence_context,
    list_documents,
]
