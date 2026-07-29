"""Persistent vector store backed by Chroma.

Provided as working boilerplate: ingestion writes here, and the `search`
function is what the agents' retrieval tools call under the hood. Candidates
can replace Chroma with any store; keep the `add` / `search` interface stable
so the agent tools keep working.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import re

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.ingestion.chunker import Chunk
from app.services.embeddings import embed_query, embed_texts

_COLLECTION = "documents"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_RRF_K = 60


@dataclass
class SearchHit:
    doc_id: str
    filename: str
    chunk_id: str
    text: str
    score: float
    order: int | None = None


@dataclass
class StoredChunk:
    doc_id: str
    filename: str
    chunk_id: str
    text: str
    order: int


@dataclass
class IndexedDocument:
    doc_id: str
    filename: str
    chunk_count: int


def _tokenize(value: str) -> list[str]:
    """Return lowercase alphanumeric terms for lexical ranking."""

    return _TOKEN_PATTERN.findall(value.lower())


def _keyword_ranking(query: str, chunks: list[StoredChunk]) -> list[str]:
    """Rank chunks containing query terms with BM25."""

    query_tokens = _tokenize(query)
    if not query_tokens or not chunks:
        return []

    corpus = [
        _tokenize(f"{chunk.filename} {chunk.text}")
        for chunk in chunks
    ]
    query_terms = set(query_tokens)
    matching_indexes = [
        index
        for index, tokens in enumerate(corpus)
        if query_terms.intersection(tokens)
    ]
    if not matching_indexes:
        return []

    scores = BM25Okapi(corpus).get_scores(query_tokens)
    ranked_indexes = sorted(
        matching_indexes,
        key=lambda index: (-float(scores[index]), index),
    )
    return [chunks[index].chunk_id for index in ranked_indexes]


def _reciprocal_rank_fusion(
    rankings: list[list[str]],
    *,
    rank_constant: int = _RRF_K,
) -> dict[str, float]:
    """Fuse ranked chunk IDs and normalize scores to a zero-to-one range."""

    active_rankings = [ranking for ranking in rankings if ranking]
    if not active_rankings:
        return {}

    scores: defaultdict[str, float] = defaultdict(float)
    for ranking in active_rankings:
        seen: set[str] = set()
        for rank, chunk_id in enumerate(ranking, start=1):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] += 1.0 / (rank_constant + rank)

    maximum = len(active_rankings) / (rank_constant + 1)
    return {
        chunk_id: score / maximum
        for chunk_id, score in scores.items()
    }


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

    def list_documents(self, doc_ids: list[str] | None = None) -> list[IndexedDocument]:
        """Summarize indexed documents from their stored chunk metadata."""

        kwargs = {"include": ["metadatas"]}
        if doc_ids is not None:
            kwargs["where"] = {"doc_id": {"$in": doc_ids}}
        result = self._collection.get(**kwargs)
        counts: dict[tuple[str, str], int] = {}
        for meta in result.get("metadatas") or []:
            key = (
                str(meta.get("doc_id", "")),
                str(meta.get("filename", "")),
            )
            counts[key] = counts.get(key, 0) + 1
        return sorted(
            (
                IndexedDocument(doc_id=doc_id, filename=filename, chunk_count=count)
                for (doc_id, filename), count in counts.items()
                if doc_id and filename
            ),
            key=lambda document: (document.filename.lower(), document.doc_id),
        )

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
                    order=int(meta["order"]) if meta.get("order") is not None else None,
                )
            )
        return hits

    def get_context(
        self,
        doc_id: str,
        chunk_order: int,
        before: int = 1,
        after: int = 1,
    ) -> list[StoredChunk]:
        """Return an ordered, bounded chunk window from one document."""

        result = self._collection.get(
            where={"doc_id": doc_id},
            include=["documents", "metadatas"],
        )
        ids = result.get("ids") or []
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        first_order = max(0, chunk_order - before)
        last_order = chunk_order + after
        chunks = []
        for chunk_id, text, meta in zip(ids, docs, metas):
            order = int(meta.get("order", -1))
            if first_order <= order <= last_order:
                chunks.append(
                    StoredChunk(
                        doc_id=str(meta.get("doc_id", "")),
                        filename=str(meta.get("filename", "")),
                        chunk_id=str(chunk_id),
                        text=str(text),
                        order=order,
                    )
                )
        return sorted(chunks, key=lambda chunk: chunk.order)


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
