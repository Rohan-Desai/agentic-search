from app.agents.evidence_ledger import EvidenceLedger
from app.models.research import (
    AttemptStatus,
    EvidenceCandidate,
    ResearchBudget,
    ResearchContext,
    ResearchUsage,
)
from app.services.document_catalog_service import execute_document_list
from app.services.retrieval_service import (
    execute_context_inspection,
    execute_evidence_search,
)
from app.services.vector_store import IndexedDocument, SearchHit, StoredChunk


class FakeStore:
    def __init__(
        self,
        *,
        hits: list[SearchHit] | None = None,
        chunks: list[StoredChunk] | None = None,
    ) -> None:
        self.hits = hits or []
        self.chunks = chunks or []
        self.search_calls = 0
        self.catalog_calls = 0

    def search(self, query, top_k=5, doc_ids=None):
        self.search_calls += 1
        return self.hits

    def get_context(self, doc_id, chunk_order, before=1, after=1):
        return self.chunks

    def list_documents(self, doc_ids=None):
        self.catalog_calls += 1
        return [IndexedDocument(doc_id="doc-1", filename="one.pdf", chunk_count=1)]


def hit(index: int, text: str = "evidence") -> SearchHit:
    return SearchHit(
        doc_id="doc-1",
        filename="one.pdf",
        chunk_id=f"chunk-{index}",
        text=text,
        score=0.9,
        order=index,
    )


def context(
    *,
    budget: ResearchBudget | None = None,
    usage: ResearchUsage | None = None,
) -> ResearchContext:
    return ResearchContext(
        request_id="request-1",
        original_query="Question",
        budget=budget or ResearchBudget(),
        usage=usage or ResearchUsage(),
    )


def test_search_and_tool_limits_block_provider_calls() -> None:
    tool_limited = context(
        budget=ResearchBudget(max_tool_calls=1),
        usage=ResearchUsage(tool_calls=1),
    )
    tool_store = FakeStore(hits=[hit(1)])
    tool_result = execute_evidence_search(
        context=tool_limited,
        ledger=EvidenceLedger(tool_limited),
        query="query",
        store=tool_store,
    )
    assert tool_result.status is AttemptStatus.INVALID
    assert tool_result.error_code == "tool_budget_exhausted"
    assert tool_store.search_calls == 0

    search_limited = context(
        budget=ResearchBudget(max_searches=1),
        usage=ResearchUsage(searches=1),
    )
    search_store = FakeStore(hits=[hit(1)])
    search_result = execute_evidence_search(
        context=search_limited,
        ledger=EvidenceLedger(search_limited),
        query="query",
        store=search_store,
    )
    assert search_result.error_code == "search_budget_exhausted"
    assert search_store.search_calls == 0


def test_document_catalog_obeys_shared_tool_limit() -> None:
    research = context(
        budget=ResearchBudget(max_tool_calls=1),
        usage=ResearchUsage(tool_calls=1),
    )
    store = FakeStore()

    result = execute_document_list(context=research, store=store)

    assert result.status is AttemptStatus.INVALID
    assert result.error_code == "tool_budget_exhausted"
    assert store.catalog_calls == 0


def test_evidence_and_context_limits_truncate_before_ledger_registration() -> None:
    research = context(
        budget=ResearchBudget(max_evidence=1, max_context_chars=5)
    )
    store = FakeStore(hits=[hit(1, "12345"), hit(2, "67890")])

    result = execute_evidence_search(
        context=research,
        ledger=EvidenceLedger(research),
        query="query",
        top_k=2,
        store=store,
    )

    assert result.status is AttemptStatus.SUCCEEDED
    assert result.error_code == "evidence_budget_exhausted"
    assert [item.chunk_id for item in research.evidence] == ["chunk-1"]
    assert research.usage.evidence_count == 1
    assert research.usage.context_chars == 5


def test_context_char_limit_can_reject_all_new_results() -> None:
    research = context(
        budget=ResearchBudget(max_context_chars=4)
    )

    result = execute_evidence_search(
        context=research,
        ledger=EvidenceLedger(research),
        query="query",
        store=FakeStore(hits=[hit(1, "12345")]),
    )

    assert result.status is AttemptStatus.INVALID
    assert result.error_code == "context_budget_exhausted"
    assert research.evidence == []


def test_repeated_no_progress_searches_block_the_next_search() -> None:
    research = context(
        budget=ResearchBudget(no_progress_limit=2)
    )
    store = FakeStore(hits=[])
    ledger = EvidenceLedger(research)

    first = execute_evidence_search(
        context=research, ledger=ledger, query="first", store=store
    )
    second = execute_evidence_search(
        context=research, ledger=ledger, query="second", store=store
    )
    third = execute_evidence_search(
        context=research, ledger=ledger, query="third", store=store
    )

    assert first.status is AttemptStatus.EMPTY
    assert second.status is AttemptStatus.EMPTY
    assert third.status is AttemptStatus.INVALID
    assert third.error_code == "no_progress_limit_reached"
    assert store.search_calls == 2
    assert research.usage.consecutive_no_progress == 2


def test_context_inspection_obeys_evidence_limits() -> None:
    research = context(
        budget=ResearchBudget(max_evidence=1)
    )
    ledger = EvidenceLedger(research)
    ledger.add(
        EvidenceCandidate(
            doc_id="doc-1",
            filename="one.pdf",
            chunk_id="chunk-0",
            text="source",
            query="query",
            location={"chunk_order": 0},
        )
    )

    result = execute_context_inspection(
        context=research,
        ledger=ledger,
        evidence_id="E1",
        store=FakeStore(
            chunks=[
                StoredChunk(
                    doc_id="doc-1",
                    filename="one.pdf",
                    chunk_id="chunk-1",
                    text="adjacent",
                    order=1,
                )
            ]
        ),
    )

    assert result.status is AttemptStatus.INVALID
    assert result.error_code == "evidence_budget_exhausted"
    assert len(research.evidence) == 1
