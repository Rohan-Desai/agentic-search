"""Orchestrates parse -> chunk -> embed -> store for uploaded files."""
import uuid
from pathlib import Path

from app.core.logging import get_logger
from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import parse
from app.models.schemas import IngestedDocument
from app.services.vector_store import get_vector_store

logger = get_logger(__name__)


def ingest_file(path: Path) -> IngestedDocument:
    doc_id = uuid.uuid4().hex[:12]
    text, doc_type = parse(path)
    chunks = chunk_text(text, doc_id=doc_id)
    get_vector_store().add(doc_id=doc_id, filename=path.name, chunks=chunks)
    logger.info("Ingested %s (%s) -> %d chunks", path.name, doc_type.value, len(chunks))
    return IngestedDocument(
        doc_id=doc_id,
        filename=path.name,
        doc_type=doc_type,
        num_chunks=len(chunks),
    )
