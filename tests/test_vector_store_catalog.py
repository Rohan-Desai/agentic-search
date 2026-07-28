"""Tests for document summaries derived from Chroma chunk metadata."""
from app.services.vector_store import VectorStore


class FakeCollection:
    def get(self, **kwargs):
        assert kwargs == {"include": ["metadatas"]}
        return {
            "metadatas": [
                {"doc_id": "doc-2", "filename": "zeta.pdf", "order": 1},
                {"doc_id": "doc-1", "filename": "Alpha.pdf", "order": 0},
                {"doc_id": "doc-2", "filename": "zeta.pdf", "order": 0},
            ]
        }


def test_list_documents_groups_chunks_and_sorts_filenames():
    store = object.__new__(VectorStore)
    store._collection = FakeCollection()

    result = store.list_documents()

    assert [
        (document.doc_id, document.filename, document.chunk_count)
        for document in result
    ] == [
        ("doc-1", "Alpha.pdf", 1),
        ("doc-2", "zeta.pdf", 2),
    ]
