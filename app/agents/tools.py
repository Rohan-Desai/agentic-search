"""Function tools exposed to the agents.

These are FULLY IMPLEMENTED and ready to use. They wrap the vector store and
document services so that agents you build can retrieve and inspect documents.
You are encouraged to add more tools (e.g. table lookup, cross-document
comparison, summarization) — this file is the natural place for them.

Tools are declared with the OpenAI Agents SDK `@function_tool` decorator, which
auto-generates the JSON schema from the type hints and docstring.
"""
from __future__ import annotations

from agents import function_tool

from app.services.vector_store import get_vector_store


@function_tool
def search_documents(query: str, top_k: int = 5) -> str:
    """Hybrid search across all ingested documents.

    Args:
        query: A natural-language search query.
        top_k: How many chunks to return (1-20).

    Returns:
        A formatted list of matching passages with their document id, filename,
        hybrid rank score, and text. Use these to ground your answer and to cite
        sources by doc_id/filename.
    """
    top_k = max(1, min(top_k, 20))
    hits = get_vector_store().search(query=query, top_k=top_k)
    if not hits:
        return "No matching passages found."
    lines = []
    for h in hits:
        lines.append(
            f"- doc_id={h.doc_id} | file={h.filename} | score={h.score:.3f}\n"
            f"  chunk_id={h.chunk_id}\n  text: {h.text}"
        )
    return "\n".join(lines)


@function_tool
def search_within_documents(query: str, doc_ids: list[str], top_k: int = 5) -> str:
    """Hybrid search restricted to a specific set of documents.

    Args:
        query: A natural-language search query.
        doc_ids: Restrict search to these document ids.
        top_k: How many chunks to return (1-20).
    """
    top_k = max(1, min(top_k, 20))
    hits = get_vector_store().search(query=query, top_k=top_k, doc_ids=doc_ids)
    if not hits:
        return "No matching passages found in the specified documents."
    return "\n".join(
        f"- doc_id={h.doc_id} | file={h.filename} | score={h.score:.3f}\n  text: {h.text}"
        for h in hits
    )


# Convenience export: pass this list to an Agent's `tools=` argument.
RETRIEVAL_TOOLS = [search_documents, search_within_documents]
