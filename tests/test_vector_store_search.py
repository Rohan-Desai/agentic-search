"""Tests for hybrid search inside the Chroma-backed vector-store boundary."""

from app.services import vector_store
from app.services.vector_store import VectorStore


class FakeCollection:
    def __init__(self, chunks, semantic_ids):
        self.chunks = chunks
        self.semantic_ids = semantic_ids
        self.get_calls = []
        self.query_calls = []

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return {
            "ids": [item["chunk_id"] for item in self.chunks],
            "documents": [item["text"] for item in self.chunks],
            "metadatas": [
                {
                    "doc_id": item["doc_id"],
                    "filename": item["filename"],
                    "order": item["order"],
                }
                for item in self.chunks
            ],
        }

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {"ids": [self.semantic_ids]}


def stored(
    chunk_id,
    text,
    *,
    doc_id="doc-1",
    filename="document.txt",
    order=0,
):
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "filename": filename,
        "text": text,
        "order": order,
    }


def store_with(collection):
    store = object.__new__(VectorStore)
    store._collection = collection
    return store


def test_hybrid_search_promotes_strong_exact_match(monkeypatch):
    collection = FakeCollection(
        chunks=[
            stored(
                "policy::0",
                "General safety responsibilities and expectations.",
                doc_id="policy",
                filename="Health_and_Safety_Policy.pdf",
            ),
            stored(
                "log::0",
                "Sagebrush incident occurred in 2023.",
                doc_id="log",
                filename="Safety_Incident_Log.xlsx",
            ),
            stored(
                "incident::0",
                "Corrective actions included LOTO retraining.",
                doc_id="incident",
                filename="Incident_Report_Sagebrush_Aug2023.docx",
            ),
        ],
        semantic_ids=["policy::0", "log::0", "incident::0"],
    )
    monkeypatch.setattr(vector_store, "embed_query", lambda query: [0.1, 0.2])

    hits = store_with(collection).search(
        "Sagebrush incident corrective actions",
        top_k=2,
    )

    assert [hit.chunk_id for hit in hits] == ["incident::0", "log::0"]
    assert hits[0].score > hits[1].score
    assert 0 < hits[0].score <= 1
    assert collection.query_calls[0]["n_results"] == 3


def test_hybrid_search_applies_scope_to_both_rankings(monkeypatch):
    collection = FakeCollection(
        chunks=[
            stored(
                "allowed::0",
                "Allowed evidence.",
                doc_id="allowed",
            )
        ],
        semantic_ids=["allowed::0"],
    )
    monkeypatch.setattr(vector_store, "embed_query", lambda query: [0.1])

    hits = store_with(collection).search(
        "allowed evidence",
        top_k=5,
        doc_ids=["allowed"],
    )

    where = {"doc_id": {"$in": ["allowed"]}}
    assert [hit.chunk_id for hit in hits] == ["allowed::0"]
    assert collection.get_calls == [
        {"include": ["documents", "metadatas"], "where": where}
    ]
    assert collection.query_calls[0]["where"] == where


def test_hybrid_search_returns_empty_without_searchable_chunks(monkeypatch):
    collection = FakeCollection(chunks=[], semantic_ids=[])

    def unexpected_embedding(query):
        raise AssertionError("empty search should not embed the query")

    monkeypatch.setattr(vector_store, "embed_query", unexpected_embedding)

    assert store_with(collection).search("anything") == []
    assert collection.query_calls == []


def test_empty_document_scope_never_searches_everything(monkeypatch):
    collection = FakeCollection(
        chunks=[stored("doc::0", "Evidence.")],
        semantic_ids=["doc::0"],
    )

    def unexpected_embedding(query):
        raise AssertionError("empty scope should not embed the query")

    monkeypatch.setattr(vector_store, "embed_query", unexpected_embedding)

    assert store_with(collection).search("evidence", doc_ids=[]) == []
    assert collection.get_calls == []
    assert collection.query_calls == []
