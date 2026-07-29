"""Tests for request-scoped OpenAI Agents SDK research tools."""
import json

import pytest
from agents import RunContextWrapper

from app.agents.evidence_ledger import EvidenceLedger
from app.agents.research_tools import (
    AgentToolContext,
    inspect_evidence_context,
    list_documents,
    run_inspect_evidence_context,
    run_list_documents,
    run_search_evidence,
    search_evidence,
)
from app.models.research import (
    AttemptStatus,
    ContextInspectionResult,
    DocumentListResult,
    EvidenceSearchResult,
    ResearchContext,
)
from app.services.vector_store import IndexedDocument, SearchHit, StoredChunk


class FakeStore:
    def __init__(
        self,
        hits: list[SearchHit] | None = None,
        error: Exception | None = None,
        context_chunks: list[StoredChunk] | None = None,
        context_error: Exception | None = None,
        documents: list[IndexedDocument] | None = None,
        catalog_error: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.error = error
        self.context_chunks = context_chunks or []
        self.context_error = context_error
        self.documents = documents or []
        self.catalog_error = catalog_error
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

    def get_context(
        self,
        doc_id: str,
        chunk_order: int,
        before: int = 1,
        after: int = 1,
    ) -> list[StoredChunk]:
        if self.context_error:
            raise self.context_error
        return self.context_chunks

    def list_documents(
        self,
        doc_ids: list[str] | None = None,
    ) -> list[IndexedDocument]:
        if self.catalog_error:
            raise self.catalog_error
        if doc_ids is None:
            return self.documents
        return [document for document in self.documents if document.doc_id in doc_ids]


def hit(doc_id: str = "doc-1", chunk_id: str = "doc-1::0") -> SearchHit:
    return SearchHit(
        doc_id=doc_id,
        filename="operations.docx",
        chunk_id=chunk_id,
        text="Coral Bay available capacity was 82 MW.",
        score=0.91,
        order=0,
    )


def research_context(
    request_id: str = "req-1",
    authorized_doc_ids: list[str] | None = None,
) -> ResearchContext:
    return ResearchContext(
        request_id=request_id,
        original_query="What was Coral Bay's available capacity?",
        authorized_doc_ids=authorized_doc_ids,
    )


def test_tool_schema_exposes_only_model_controlled_arguments():
    properties = search_evidence.params_json_schema["properties"]

    assert set(properties) == {"query", "doc_ids"}
    assert "wrapper" not in properties
    assert "context" not in properties
    assert search_evidence.name == "search_evidence"


def test_application_handler_updates_request_scoped_state():
    research = research_context(authorized_doc_ids=["doc-1"])
    tool_context = AgentToolContext.create(research, store=FakeStore([hit()]))

    result = run_search_evidence(
        tool_context,
        query="Coral Bay derated capacity",
        doc_ids=["doc-1"],
        top_k=3,
    )

    assert result.status is AttemptStatus.SUCCEEDED
    assert result.evidence[0].evidence_id == "E1"
    assert research.evidence[0].evidence_id == "E1"
    assert research.attempts[0].result_evidence_ids == ["E1"]
    assert len(research.attempts) == 1


@pytest.mark.asyncio
async def test_sdk_tool_invocation_returns_structured_json():
    research = research_context()
    tool_context = AgentToolContext.create(research, store=FakeStore([hit()]))
    wrapper = RunContextWrapper(context=tool_context)

    output = await search_evidence.on_invoke_tool(
        wrapper,
        json.dumps(
            {
                "query": "Coral Bay capacity",
                "doc_ids": None,
                "top_k": 5,
            }
        ),
    )
    result = EvidenceSearchResult.model_validate_json(output)

    assert result.status is AttemptStatus.SUCCEEDED
    assert result.evidence[0].evidence_id == "E1"
    assert result.new_evidence_count == 1


def test_tool_contexts_keep_research_runs_isolated():
    first_research = research_context("req-1")
    second_research = research_context("req-2")
    first = AgentToolContext.create(first_research, store=FakeStore([hit()]))
    second = AgentToolContext.create(
        second_research,
        store=FakeStore([hit(doc_id="doc-2", chunk_id="doc-2::0")]),
    )

    run_search_evidence(first, query="first query")
    run_search_evidence(second, query="second query")

    assert [item.doc_id for item in first_research.evidence] == ["doc-1"]
    assert [item.doc_id for item in second_research.evidence] == ["doc-2"]
    assert first_research.evidence is not second_research.evidence


def test_tool_returns_safe_structured_failure():
    research = research_context()
    tool_context = AgentToolContext.create(
        research,
        store=FakeStore(error=RuntimeError("private provider detail")),
    )

    result = run_search_evidence(tool_context, query="query")

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "retrieval_failed"
    assert "private provider detail" not in result.model_dump_json()
    assert research.attempts[0].status is AttemptStatus.FAILED


def test_tool_cannot_widen_authorized_scope():
    research = research_context(authorized_doc_ids=["doc-1"])
    store = FakeStore([hit()])
    tool_context = AgentToolContext.create(research, store=store)

    result = run_search_evidence(
        tool_context,
        query="query",
        doc_ids=["doc-2"],
    )

    assert result.status is AttemptStatus.INVALID
    assert result.error_code == "scope_not_authorized"
    assert store.calls == []


def test_tool_context_rejects_ledger_from_another_request():
    first = research_context("req-1")
    second = research_context("req-2")

    with pytest.raises(ValueError, match="same research context"):
        AgentToolContext(
            research=first,
            ledger=EvidenceLedger(second),
        )


def test_context_tool_schema_exposes_only_bounded_lookup_arguments():
    properties = inspect_evidence_context.params_json_schema["properties"]

    assert set(properties) == {"evidence_id", "before", "after"}
    assert "wrapper" not in properties


@pytest.mark.asyncio
async def test_sdk_context_tool_registers_neighboring_evidence():
    research = research_context()
    store = FakeStore(
        hits=[hit()],
        context_chunks=[
            StoredChunk(
                doc_id="doc-1",
                filename="operations.docx",
                chunk_id="doc-1::0",
                text=hit().text,
                order=0,
            ),
            StoredChunk(
                doc_id="doc-1",
                filename="operations.docx",
                chunk_id="doc-1::1",
                text="The derating began in March.",
                order=1,
            ),
        ],
    )
    tool_context = AgentToolContext.create(research, store=store)
    source_id = run_search_evidence(tool_context, query="capacity").evidence[0].evidence_id
    wrapper = RunContextWrapper(context=tool_context)

    output = await inspect_evidence_context.on_invoke_tool(
        wrapper,
        json.dumps({"evidence_id": source_id, "before": 1, "after": 1}),
    )
    result = ContextInspectionResult.model_validate_json(output)

    assert result.status is AttemptStatus.SUCCEEDED
    assert result.new_evidence_count == 1
    assert [item.evidence_id for item in result.evidence] == ["E1", "E2"]


def test_context_tool_returns_safe_failure():
    research = research_context()
    store = FakeStore(hits=[hit()], context_error=RuntimeError("private detail"))
    tool_context = AgentToolContext.create(research, store=store)
    source_id = run_search_evidence(tool_context, query="capacity").evidence[0].evidence_id

    result = run_inspect_evidence_context(
        tool_context,
        evidence_id=source_id,
    )

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "context_retrieval_failed"
    assert "private detail" not in result.model_dump_json()


def test_list_documents_tool_has_no_model_controlled_arguments():
    assert list_documents.params_json_schema["properties"] == {}


@pytest.mark.asyncio
async def test_sdk_list_documents_tool_returns_authorized_catalog():
    research = research_context(authorized_doc_ids=["doc-2"])
    tool_context = AgentToolContext.create(
        research,
        store=FakeStore(
            documents=[
                IndexedDocument("doc-1", "annual-report.pdf", 10),
                IndexedDocument("doc-2", "operations.docx", 4),
            ]
        ),
    )

    output = await list_documents.on_invoke_tool(
        RunContextWrapper(context=tool_context),
        "{}",
    )
    result = DocumentListResult.model_validate_json(output)

    assert result.status is AttemptStatus.SUCCEEDED
    assert [document.doc_id for document in result.documents] == ["doc-2"]
    assert research.attempts[-1].tool_name == "list_documents"
    assert len(research.attempts) == 1


def test_list_documents_tool_returns_safe_failure():
    research = research_context()
    tool_context = AgentToolContext.create(
        research,
        store=FakeStore(catalog_error=RuntimeError("private detail")),
    )

    result = run_list_documents(tool_context)

    assert result.status is AttemptStatus.FAILED
    assert result.error_code == "document_catalog_failed"
    assert "private detail" not in result.model_dump_json()
