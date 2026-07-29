"""Structured retrieval boundary for agentic research."""
from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from app.agents.evidence_ledger import EvidenceLedger
from app.agents.evidence_ledger import UnknownEvidenceError
from app.models.research import (
    AttemptStatus,
    ContextInspectionResult,
    EvidenceCandidate,
    EvidenceLocation,
    EvidenceSearchItem,
    EvidenceSearchResult,
    ResearchContext,
    SearchAttempt,
)
from app.services.vector_store import IndexedDocument, SearchHit, StoredChunk, get_vector_store

_MIN_TOP_K = 1
_MAX_TOP_K = 20
_MAX_CONTEXT_WINDOW = 2


class SearchStore(Protocol):
    """Small vector-store interface needed by structured retrieval."""

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[SearchHit]: ...

    def get_context(
        self,
        doc_id: str,
        chunk_order: int,
        before: int = 1,
        after: int = 1,
    ) -> list[StoredChunk]: ...

    def list_documents(self, doc_ids: list[str] | None = None) -> list[IndexedDocument]: ...


class RetrievalExecutionError(RuntimeError):
    """The storage or embedding boundary failed during a search."""


def execute_evidence_search(
    *,
    context: ResearchContext,
    ledger: EvidenceLedger,
    query: str,
    requested_doc_ids: list[str] | None = None,
    top_k: int = 5,
    store: SearchStore | None = None,
    clock: Callable[[], float] = perf_counter,
) -> EvidenceSearchResult:
    """Search, register canonical evidence, and record one attempt."""

    effective_doc_ids, scope_valid = _effective_scope(
        context.authorized_doc_ids, requested_doc_ids
    )
    bounded_top_k = max(_MIN_TOP_K, min(top_k, _MAX_TOP_K))
    started_at = clock()

    if not scope_valid:
        duration_ms = _elapsed_ms(started_at, clock)
        _record_attempt(
            context=context,
            tool_name="search_evidence",
            query=query,
            requested_doc_ids=requested_doc_ids,
            effective_doc_ids=[],
            status=AttemptStatus.INVALID,
            duration_ms=duration_ms,
            error_code="scope_not_authorized",
        )
        return EvidenceSearchResult(
            status=AttemptStatus.INVALID,
            query=query,
            effective_doc_ids=[],
            error_code="scope_not_authorized",
        )

    search_store = store or get_vector_store()
    try:
        hits = search_store.search(
            query=query,
            top_k=bounded_top_k,
            doc_ids=effective_doc_ids,
        )
    except Exception as exc:
        duration_ms = _elapsed_ms(started_at, clock)
        _record_attempt(
            context=context,
            tool_name="search_evidence",
            query=query,
            requested_doc_ids=requested_doc_ids,
            effective_doc_ids=effective_doc_ids,
            status=AttemptStatus.FAILED,
            duration_ms=duration_ms,
            error_code="retrieval_failed",
        )
        raise RetrievalExecutionError("Evidence retrieval failed.") from exc

    candidates = [
        EvidenceCandidate(
            doc_id=hit.doc_id,
            filename=hit.filename,
            chunk_id=hit.chunk_id,
            text=hit.text,
            query=query,
            retrieval_score=hit.score,
            location=EvidenceLocation(chunk_order=hit.order),
        )
        for hit in hits
    ]
    additions = ledger.add_many(candidates)
    items = [
        EvidenceSearchItem(
            evidence_id=addition.evidence_id,
            doc_id=hit.doc_id,
            filename=hit.filename,
            chunk_id=hit.chunk_id,
            text=hit.text,
            retrieval_score=hit.score,
            location=EvidenceLocation(chunk_order=hit.order),
            is_new=addition.is_new,
        )
        for hit, addition in zip(hits, additions)
    ]
    new_evidence_count = sum(item.is_new for item in additions)
    status = AttemptStatus.SUCCEEDED if items else AttemptStatus.EMPTY
    duration_ms = _elapsed_ms(started_at, clock)
    _record_attempt(
        context=context,
        tool_name="search_evidence",
        query=query,
        requested_doc_ids=requested_doc_ids,
        effective_doc_ids=effective_doc_ids,
        status=status,
        duration_ms=duration_ms,
        result_evidence_ids=[item.evidence_id for item in items],
        new_evidence_count=new_evidence_count,
    )
    return EvidenceSearchResult(
        status=status,
        query=query,
        effective_doc_ids=effective_doc_ids,
        evidence=items,
        new_evidence_count=new_evidence_count,
    )


def execute_context_inspection(
    *,
    context: ResearchContext,
    ledger: EvidenceLedger,
    evidence_id: str,
    before: int = 1,
    after: int = 1,
    store: SearchStore | None = None,
    clock: Callable[[], float] = perf_counter,
) -> ContextInspectionResult:
    """Retrieve and register a bounded window around known evidence."""

    bounded_before = max(0, min(before, _MAX_CONTEXT_WINDOW))
    bounded_after = max(0, min(after, _MAX_CONTEXT_WINDOW))
    started_at = clock()

    try:
        source = ledger.get(evidence_id)
    except UnknownEvidenceError:
        _record_attempt(
            context=context,
            tool_name="inspect_evidence_context",
            query=None,
            requested_doc_ids=None,
            effective_doc_ids=None,
            status=AttemptStatus.INVALID,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code="unknown_evidence",
        )
        return ContextInspectionResult(
            status=AttemptStatus.INVALID,
            source_evidence_id=evidence_id,
            error_code="unknown_evidence",
        )

    if source.location.chunk_order is None:
        _record_attempt(
            context=context,
            tool_name="inspect_evidence_context",
            query=None,
            requested_doc_ids=[source.doc_id],
            effective_doc_ids=[source.doc_id],
            status=AttemptStatus.INVALID,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code="missing_chunk_order",
        )
        return ContextInspectionResult(
            status=AttemptStatus.INVALID,
            source_evidence_id=evidence_id,
            error_code="missing_chunk_order",
        )

    if (
        context.authorized_doc_ids is not None
        and source.doc_id not in context.authorized_doc_ids
    ):
        _record_attempt(
            context=context,
            tool_name="inspect_evidence_context",
            query=None,
            requested_doc_ids=[source.doc_id],
            effective_doc_ids=[],
            status=AttemptStatus.INVALID,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code="evidence_outside_scope",
        )
        return ContextInspectionResult(
            status=AttemptStatus.INVALID,
            source_evidence_id=evidence_id,
            error_code="evidence_outside_scope",
        )

    search_store = store or get_vector_store()
    try:
        chunks = search_store.get_context(
            doc_id=source.doc_id,
            chunk_order=source.location.chunk_order,
            before=bounded_before,
            after=bounded_after,
        )
    except Exception as exc:
        _record_attempt(
            context=context,
            tool_name="inspect_evidence_context",
            query=None,
            requested_doc_ids=[source.doc_id],
            effective_doc_ids=[source.doc_id],
            status=AttemptStatus.FAILED,
            duration_ms=_elapsed_ms(started_at, clock),
            error_code="context_retrieval_failed",
        )
        raise RetrievalExecutionError("Evidence context retrieval failed.") from exc

    discovery_query = f"context:{evidence_id}"
    candidates = [
        EvidenceCandidate(
            doc_id=chunk.doc_id,
            filename=chunk.filename,
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            query=discovery_query,
            location=EvidenceLocation(chunk_order=chunk.order),
        )
        for chunk in chunks
    ]
    additions = ledger.add_many(candidates)
    items = [
        EvidenceSearchItem(
            evidence_id=addition.evidence_id,
            doc_id=chunk.doc_id,
            filename=chunk.filename,
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            location=EvidenceLocation(chunk_order=chunk.order),
            is_new=addition.is_new,
        )
        for chunk, addition in zip(chunks, additions)
    ]
    new_evidence_count = sum(item.is_new for item in additions)
    status = AttemptStatus.SUCCEEDED if items else AttemptStatus.EMPTY
    _record_attempt(
        context=context,
        tool_name="inspect_evidence_context",
        query=None,
        requested_doc_ids=[source.doc_id],
        effective_doc_ids=[source.doc_id],
        status=status,
        duration_ms=_elapsed_ms(started_at, clock),
        result_evidence_ids=[item.evidence_id for item in items],
        new_evidence_count=new_evidence_count,
    )
    return ContextInspectionResult(
        status=status,
        source_evidence_id=evidence_id,
        evidence=items,
        new_evidence_count=new_evidence_count,
    )


def _effective_scope(
    authorized_doc_ids: list[str] | None,
    requested_doc_ids: list[str] | None,
) -> tuple[list[str] | None, bool]:
    """Return the allowed intersection and whether the request is valid."""

    if authorized_doc_ids is None:
        requested = _unique(requested_doc_ids)
        return requested, requested is None or bool(requested)
    if requested_doc_ids is None:
        authorized = _unique(authorized_doc_ids)
        return authorized, bool(authorized)

    authorized = set(authorized_doc_ids)
    effective = [doc_id for doc_id in _unique(requested_doc_ids) or [] if doc_id in authorized]
    return effective, bool(effective)


def _unique(doc_ids: list[str] | None) -> list[str] | None:
    if doc_ids is None:
        return None
    return list(dict.fromkeys(doc_ids))


def _elapsed_ms(started_at: float, clock: Callable[[], float]) -> int:
    return max(0, round((clock() - started_at) * 1000))


def _record_attempt(
    *,
    context: ResearchContext,
    tool_name: str,
    query: str,
    requested_doc_ids: list[str] | None,
    effective_doc_ids: list[str] | None,
    status: AttemptStatus,
    duration_ms: int,
    result_evidence_ids: list[str] | None = None,
    new_evidence_count: int = 0,
    error_code: str | None = None,
) -> None:
    context.attempts.append(
        SearchAttempt(
            tool_name=tool_name,
            query=query,
            requested_doc_ids=requested_doc_ids,
            effective_doc_ids=effective_doc_ids,
            result_evidence_ids=result_evidence_ids or [],
            new_evidence_count=new_evidence_count,
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
        )
    )
