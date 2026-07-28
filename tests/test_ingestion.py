"""Ingestion unit tests that don't require network / API keys."""
from app.ingestion.chunker import chunk_text


def test_chunker_splits_and_orders():
    text = "\n".join(f"Paragraph number {i} with some content." for i in range(50))
    chunks = chunk_text(text, doc_id="abc", max_chars=200, overlap=20)
    assert len(chunks) > 1
    assert all(c.chunk_id.startswith("abc::") for c in chunks)
    assert [c.order for c in chunks] == list(range(len(chunks)))


def test_chunker_empty():
    assert chunk_text("", doc_id="x") == []
