"""Persistent vector store backed by Chroma.

Provided as working boilerplate: ingestion writes here, and the `search`
function is what the agents' retrieval tools call under the hood. Candidates
can replace Chroma with any store; keep the `add` / `search` interface stable
so the agent tools keep working.
"""
from __future__ import annotations

from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.ingestion.chunker import Chunk
from app.services.embeddings import embed_query, embed_texts

_COLLECTION = "documents"


@dataclass
class SearchHit:
    doc_id: str
    filename: str
    chunk_id: str
    text: str
    score: float


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(
            path=str(settings.vector_store_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def add(self, doc_id: str, filename: str, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        embeddings = embed_texts([c.text for c in chunks])
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[{"doc_id": doc_id, "filename": filename, "order": c.order} for c in chunks],
        )

    def existing_filenames(self) -> set[str]:
        """Return the set of filenames that already have chunks in the store.

        Used by the seed script to skip documents that were already ingested,
        so a re-run after an interrupted seed only processes what's missing.
        """
        # Pull just metadata (no embeddings/documents) to keep this light.
        result = self._collection.get(include=["metadatas"])
        metas = result.get("metadatas") or []
        return {str(m.get("filename")) for m in metas if m and m.get("filename")}

    def count(self) -> int:
        """Total number of chunks currently stored."""
        return self._collection.count()

    def search(
        self, query: str, top_k: int = 5, doc_ids: list[str] | None = None
    ) -> list[SearchHit]:
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        result = self._collection.query(
            query_embeddings=[embed_query(query)],
            n_results=top_k,
            where=where,
        )
        hits: list[SearchHit] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        for cid, text, meta, dist in zip(ids, docs, metas, dists):
            hits.append(
                SearchHit(
                    doc_id=str(meta.get("doc_id", "")),
                    filename=str(meta.get("filename", "")),
                    chunk_id=cid,
                    text=text,
                    score=1.0 - float(dist),  # cosine distance -> similarity
                )
            )
        return hits


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
