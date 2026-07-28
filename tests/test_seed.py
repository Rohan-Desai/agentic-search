"""Tests for seed-corpus discovery and vector-store idempotency (no API calls)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.seed import discover_files


def test_discover_files_filters_and_recurses():
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        (dp / "a.pdf").write_text("x")
        (dp / "b.docx").write_text("x")
        (dp / "notes.txt").write_text("x")  # unsupported
        (dp / "sub").mkdir()
        (dp / "sub" / "c.csv").write_text("x")
        names = sorted(f.name for f in discover_files(dp))
        assert names == ["a.pdf", "b.docx", "c.csv"]


def test_discover_files_missing_dir():
    assert discover_files(Path("/does/not/exist")) == []


def test_existing_filenames_enables_skip():
    """A file already in the store is reported so seeding can skip it."""

    def fake_embed(texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    with tempfile.TemporaryDirectory() as tmp, patch(
        "app.services.vector_store.embed_texts", side_effect=fake_embed
    ):
        import app.services.vector_store as vs
        from app.core.config import get_settings

        # Point the store at a throwaway directory.
        get_settings.cache_clear()
        settings = get_settings()
        settings.vector_store_dir = Path(tmp)
        vs._store = None

        store = vs.VectorStore()
        from app.ingestion.chunker import chunk_text

        store.add("doc1", "report.pdf", chunk_text("A short test document.", doc_id="doc1"))
        assert "report.pdf" in store.existing_filenames()
        assert store.count() >= 1
