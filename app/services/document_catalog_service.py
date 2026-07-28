"""Request-scoped document catalog for agentic research."""
from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from app.models.research import (
    AttemptStatus,
    DocumentCatalogItem,
    DocumentListResult,
    ResearchContext,
    SearchAttempt,
)
from app.services.retrieval_service import SearchStore
from app.services.research_budget_service import reserve_tool_call
from app.services.vector_store import get_vector_store

_MAX_DOCUMENTS = 100


class DocumentCatalogError(RuntimeError):
    """The document catalog could not be read."""


def execute_document_list(
    *,
    context: ResearchContext,
    store: SearchStore | None = None,
    clock: Callable[[], float] = perf_counter,
) -> DocumentListResult:
    """List documents inside the request's authorized scope."""

    started_at = clock()
    effective_doc_ids = context.authorized_doc_ids
    budget_error = reserve_tool_call(context)
    if budget_error:
        _record_attempt(
            context=context,
            effective_doc_ids=effective_doc_ids,
            status=AttemptStatus.INVALID,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code=budget_error,
        )
        return DocumentListResult(
            status=AttemptStatus.INVALID,
            error_code=budget_error,
        )

    if effective_doc_ids == []:
        _record_attempt(
            context=context,
            effective_doc_ids=[],
            status=AttemptStatus.EMPTY,
            duration_ms=_elapsed_ms(started_at, clock),
        )
        return DocumentListResult(status=AttemptStatus.EMPTY)

    catalog_store = store or get_vector_store()
    try:
        indexed = catalog_store.list_documents(doc_ids=effective_doc_ids)
    except Exception as exc:
        _record_attempt(
            context=context,
            effective_doc_ids=effective_doc_ids,
            status=AttemptStatus.FAILED,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code="document_catalog_failed",
        )
        raise DocumentCatalogError("Document catalog lookup failed.") from exc

    truncated = len(indexed) > _MAX_DOCUMENTS
    documents = [
        DocumentCatalogItem(
            doc_id=document.doc_id,
            filename=document.filename,
            chunk_count=document.chunk_count,
        )
        for document in indexed[:_MAX_DOCUMENTS]
    ]
    status = AttemptStatus.SUCCEEDED if documents else AttemptStatus.EMPTY
    _record_attempt(
        context=context,
        effective_doc_ids=effective_doc_ids,
        status=status,
        duration_ms=_elapsed_ms(started_at, clock),
    )
    return DocumentListResult(
        status=status,
        documents=documents,
        truncated=truncated,
    )


def _elapsed_ms(started_at: float, clock: Callable[[], float]) -> int:
    return max(0, round((clock() - started_at) * 1000))


def _record_attempt(
    *,
    context: ResearchContext,
    effective_doc_ids: list[str] | None,
    status: AttemptStatus,
    duration_ms: int,
    error_code: str | None = None,
) -> None:
    context.attempts.append(
        SearchAttempt(
            tool_name="list_documents",
            effective_doc_ids=effective_doc_ids,
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
        )
    )
