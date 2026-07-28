"""Structured retrieval boundary for agentic research."""
from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from app.agents.evidence_ledger import EvidenceLedger
from app.models.research import (
    AttemptStatus,
    EvidenceCandidate,
    EvidenceLocation,
    EvidenceSearchItem,
    EvidenceSearchResult,
    ResearchContext,
    SearchAttempt,
)
from app.services.vector_store import SearchHit, get_vector_store

_MIN_TOP_K = 1
_MAX_TOP_K = 20


class SearchStore(Protocol):
    """Small vector-store interface needed by structured retrieval."""

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[SearchHit]: ...


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
    context.usage.searches += 1

    if not scope_valid:
        duration_ms = _elapsed_ms(started_at, clock)
        _record_attempt(
            context=context,
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
            tool_name="search_evidence",
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
