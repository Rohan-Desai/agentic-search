"""Tests for bounded neighboring-chunk reads from Chroma metadata."""
from app.services.vector_store import VectorStore


class FakeCollection:
    def get(self, **kwargs):
        assert kwargs == {
            "where": {"doc_id": "doc-1"},
            "include": ["documents", "metadatas"],
        }
        return {
            "ids": ["doc-1::3", "doc-1::1", "doc-1::2", "doc-1::0"],
            "documents": ["three", "one", "two", "zero"],
            "metadatas": [
                {"doc_id": "doc-1", "filename": "report.pdf", "order": 3},
                {"doc_id": "doc-1", "filename": "report.pdf", "order": 1},
                {"doc_id": "doc-1", "filename": "report.pdf", "order": 2},
                {"doc_id": "doc-1", "filename": "report.pdf", "order": 0},
            ],
        }


def test_get_context_filters_and_orders_neighboring_chunks():
    store = object.__new__(VectorStore)
    store._collection = FakeCollection()

    chunks = store.get_context("doc-1", chunk_order=2, before=1, after=1)

    assert [chunk.order for chunk in chunks] == [1, 2, 3]
    assert [chunk.text for chunk in chunks] == ["one", "two", "three"]
