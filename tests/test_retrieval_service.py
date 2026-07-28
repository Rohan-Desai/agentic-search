"""Tests for structured, request-scoped evidence retrieval."""
from collections.abc import Iterator

import pytest

from app.agents.evidence_ledger import EvidenceLedger
from app.models.research import AttemptStatus, ResearchContext
from app.services.retrieval_service import RetrievalExecutionError, execute_evidence_search
from app.services.vector_store import SearchHit


class FakeStore:
    def __init__(
        self,
        hits: list[SearchHit] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[SearchHit]:
        self.calls.append({"query": query, "top_k": top_k, "doc_ids": doc_ids})
        if self.error:
            raise self.error
        return self.hits


def hit(
    *,
    doc_id: str = "doc-1",
    chunk_id: str = "doc-1::2",
    text: str = "2023 revenue was $100 million.",
    score: float = 0.91,
    order: int = 2,
) -> SearchHit:
    return SearchHit(
        doc_id=doc_id,
        filename="financials.xlsx",
        chunk_id=chunk_id,
        text=text,
        score=score,
        order=order,
    )


def clock_values(*values: float) -> Iterator[float]:
    return iter(values)


def test_search_registers_structured_evidence_and_attempt():
    context = ResearchContext(request_id="req-1", original_query="What was revenue?")
    store = FakeStore([hit()])
    times = clock_values(10.0, 10.025)

    result = execute_evidence_search(
        context=context,
        ledger=EvidenceLedger(context),
        query="2023 revenue",
        store=store,
        clock=lambda: next(times),
    )

    assert result.status is AttemptStatus.SUCCEEDED
    assert result.new_evidence_count == 1
    assert result.evidence[0].evidence_id == "E1"
    assert result.evidence[0].location.chunk_order == 2
    assert context.evidence[0].discoveries[0].query == "2023 revenue"
    assert context.attempts[0].result_evidence_ids == ["E1"]
    assert context.attempts[0].effective_doc_ids is None
    assert context.attempts[0].duration_ms == 25
    assert context.usage.searches == 1


def test_repeated_search_records_zero_new_evidence():
    context = ResearchContext(request_id="req-1", original_query="What was revenue?")
    ledger = EvidenceLedger(context)
    store = FakeStore([hit()])

    first = execute_evidence_search(
        context=context,
        ledger=ledger,
        query="2023 revenue",
        store=store,
    )
    second = execute_evidence_search(
        context=context,
        ledger=ledger,
        query="annual revenue 2023",
        store=store,
    )

    assert first.new_evidence_count == 1
    assert second.new_evidence_count == 0
    assert second.evidence[0].evidence_id == "E1"
    assert len(context.evidence[0].discoveries) == 2
    assert context.usage.searches == 2


def test_requested_scope_is_intersected_with_authorized_scope():
    context = ResearchContext(
        request_id="req-1",
        original_query="Question",
        authorized_doc_ids=["doc-1", "doc-2"],
    )
    store = FakeStore([])

    result = execute_evidence_search(
        context=context,
        ledger=EvidenceLedger(context),
        query="query",
        requested_doc_ids=["doc-2", "doc-3", "doc-2"],
        store=store,
        top_k=100,
    )

    assert result.effective_doc_ids == ["doc-2"]
    assert result.status is AttemptStatus.EMPTY
    assert store.calls == [{"query": "query", "top_k": 20, "doc_ids": ["doc-2"]}]


def test_fully_unauthorized_scope_is_invalid_without_searching():
    context = ResearchContext(
        request_id="req-1",
        original_query="Question",
        authorized_doc_ids=["doc-1"],
    )
    store = FakeStore([hit()])

    result = execute_evidence_search(
        context=context,
        ledger=EvidenceLedger(context),
        query="query",
        requested_doc_ids=["doc-2"],
        store=store,
    )

    assert result.status is AttemptStatus.INVALID
    assert result.error_code == "scope_not_authorized"
    assert store.calls == []
    assert context.attempts[0].status is AttemptStatus.INVALID
    assert context.attempts[0].effective_doc_ids == []
    assert context.usage.searches == 1


def test_empty_authorized_scope_never_becomes_an_unfiltered_search():
    context = ResearchContext(
        request_id="req-1",
        original_query="Question",
        authorized_doc_ids=[],
    )
    store = FakeStore([hit()])

    result = execute_evidence_search(
        context=context,
        ledger=EvidenceLedger(context),
        query="query",
        store=store,
    )

    assert result.status is AttemptStatus.INVALID
    assert result.effective_doc_ids == []
    assert store.calls == []


def test_empty_search_is_recorded_as_valid_empty_result():
    context = ResearchContext(request_id="req-1", original_query="Question")

    result = execute_evidence_search(
        context=context,
        ledger=EvidenceLedger(context),
        query="missing topic",
        store=FakeStore([]),
    )

    assert result.status is AttemptStatus.EMPTY
    assert result.evidence == []
    assert context.attempts[0].status is AttemptStatus.EMPTY
    assert context.attempts[0].error_code is None


def test_retrieval_failure_is_recorded_and_translated():
    context = ResearchContext(request_id="req-1", original_query="Question")

    with pytest.raises(RetrievalExecutionError):
        execute_evidence_search(
            context=context,
            ledger=EvidenceLedger(context),
            query="query",
            store=FakeStore(error=RuntimeError("provider unavailable")),
        )

    assert context.attempts[0].status is AttemptStatus.FAILED
    assert context.attempts[0].error_code == "retrieval_failed"
    assert context.usage.searches == 1
