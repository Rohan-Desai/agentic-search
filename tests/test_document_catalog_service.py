"""Tests for request-scoped document catalog discovery."""
import pytest

from app.models.research import AttemptStatus, ResearchContext
from app.services.document_catalog_service import (
    DocumentCatalogError,
    execute_document_list,
)
from app.services.vector_store import IndexedDocument


class FakeCatalogStore:
    def __init__(
        self,
        documents: list[IndexedDocument] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.documents = documents or []
        self.error = error
        self.calls: list[list[str] | None] = []

    def list_documents(
        self,
        doc_ids: list[str] | None = None,
    ) -> list[IndexedDocument]:
        self.calls.append(doc_ids)
        if self.error:
            raise self.error
        if doc_ids is None:
            return self.documents
        return [document for document in self.documents if document.doc_id in doc_ids]


def documents(count: int) -> list[IndexedDocument]:
    return [
        IndexedDocument(
            doc_id=f"doc-{index:03}",
            filename=f"report-{index:03}.pdf",
            chunk_count=index + 1,
        )
        for index in range(count)
    ]


def test_document_list_respects_authorized_scope_and_records_attempt():
    context = ResearchContext(
        request_id="req-1",
        original_query="What documents are available?",
        authorized_doc_ids=["doc-002"],
    )
    store = FakeCatalogStore(documents(3))

    result = execute_document_list(context=context, store=store)

    assert result.status is AttemptStatus.SUCCEEDED
    assert [document.doc_id for document in result.documents] == ["doc-002"]
    assert store.calls == [["doc-002"]]
    assert context.attempts[0].effective_doc_ids == ["doc-002"]
    assert context.usage.tool_calls == 1
    assert context.usage.evidence_count == 0


def test_empty_authorized_scope_does_not_read_unfiltered_catalog():
    context = ResearchContext(
        request_id="req-1",
        original_query="Question",
        authorized_doc_ids=[],
    )
    store = FakeCatalogStore(documents(3))

    result = execute_document_list(context=context, store=store)

    assert result.status is AttemptStatus.EMPTY
    assert result.documents == []
    assert store.calls == []


def test_document_list_is_bounded_and_reports_truncation():
    context = ResearchContext(request_id="req-1", original_query="Question")

    result = execute_document_list(
        context=context,
        store=FakeCatalogStore(documents(101)),
    )

    assert len(result.documents) == 100
    assert result.truncated is True


def test_empty_catalog_is_not_a_system_failure():
    context = ResearchContext(request_id="req-1", original_query="Question")

    result = execute_document_list(context=context, store=FakeCatalogStore())

    assert result.status is AttemptStatus.EMPTY
    assert result.error_code is None
    assert context.attempts[0].status is AttemptStatus.EMPTY


def test_catalog_failure_is_recorded_and_translated():
    context = ResearchContext(request_id="req-1", original_query="Question")

    with pytest.raises(DocumentCatalogError):
        execute_document_list(
            context=context,
            store=FakeCatalogStore(error=RuntimeError("storage unavailable")),
        )

    assert context.attempts[0].status is AttemptStatus.FAILED
    assert context.attempts[0].error_code == "document_catalog_failed"
