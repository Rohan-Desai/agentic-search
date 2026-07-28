"""MODE 1: Normal search.

The simplest mode. No agent loop required — just retrieve the most relevant
chunks and return a grounded answer. A minimal reference implementation is
provided so the system works end-to-end out of the box. You may keep, improve,
or replace it.

What "good" looks like:
  - Relevant passages retrieved from the vector store.
  - A concise answer synthesized from those passages.
  - Citations pointing back to source documents.
"""
from __future__ import annotations

from openai import OpenAI

from app.core.config import get_settings
from app.models.schemas import Citation, SearchResponse, SearchMode
from app.services.vector_store import get_vector_store


async def run_normal_search(query: str, top_k: int, doc_ids: list[str] | None) -> SearchResponse:
    settings = get_settings()
    hits = get_vector_store().search(query=query, top_k=top_k, doc_ids=doc_ids)

    context = "\n\n".join(f"[{h.filename}] {h.text}" for h in hits)
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.agent_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer the question using only the provided context. "
                    "If the answer is not in the context, say so."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    answer = completion.choices[0].message.content or ""

    citations = [
        Citation(
            doc_id=h.doc_id,
            filename=h.filename,
            chunk_id=h.chunk_id,
            snippet=h.text[:200],
            score=h.score,
        )
        for h in hits
    ]
    return SearchResponse(
        query=query,
        mode=SearchMode.NORMAL,
        answer=answer,
        citations=citations,
        steps=[],
        answer_found=bool(hits),
    )
