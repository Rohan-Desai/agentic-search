"""Seed the vector store from a fixed corpus of documents.

Place the documents to preload in `data/seed_corpus/` (PDFs, Word docs, and
spreadsheets). Running this ingests everything there into the persistent Chroma
store. It is IDEMPOTENT: files whose filename is already in the store are
skipped, so if a seed run is interrupted (or the demo process is killed) you can
re-run it and it only processes what's missing. Already-processed documents
survive because Chroma persists to disk (see VECTOR_STORE_DIR).

Usage:
    python -m scripts.seed            # ingest anything not already present
    python -m scripts.seed --force    # re-ingest every file in the corpus
    python -m scripts.seed --dir path/to/corpus

Or via Make:
    make seed
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.ingest_service import ingest_file
from app.services.vector_store import get_vector_store

logger = get_logger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv"}


def discover_files(corpus_dir: Path) -> list[Path]:
    if not corpus_dir.exists():
        return []
    return sorted(
        p
        for p in corpus_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )


def main() -> None:
    configure_logging()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Seed the vector store from a corpus.")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("data/seed_corpus"),
        help="Directory of documents to ingest (default: data/seed_corpus).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest every file even if its filename is already in the store.",
    )
    args = parser.parse_args()

    files = discover_files(args.dir)
    if not files:
        logger.warning(
            "No supported documents found in %s. "
            "Add PDFs / Word docs / spreadsheets there and re-run.",
            args.dir,
        )
        return

    store = get_vector_store()
    already = set() if args.force else store.existing_filenames()

    to_ingest = [f for f in files if f.name not in already]
    skipped = len(files) - len(to_ingest)

    logger.info(
        "Found %d document(s) in %s | already ingested: %d | to process: %d%s",
        len(files),
        args.dir,
        skipped,
        len(to_ingest),
        " (--force: re-ingesting all)" if args.force else "",
    )

    ok, failed = 0, 0
    for i, path in enumerate(to_ingest, start=1):
        try:
            doc = ingest_file(path)
            ok += 1
            logger.info(
                "[%d/%d] ingested %s -> %d chunks (doc_id=%s)",
                i, len(to_ingest), doc.filename, doc.num_chunks, doc.doc_id,
            )
        except Exception as exc:  # noqa: BLE001 — keep going; report at the end
            failed += 1
            logger.error("[%d/%d] FAILED %s: %s", i, len(to_ingest), path.name, exc)

    logger.info(
        "Seed complete. ingested=%d skipped=%d failed=%d | store now holds %d chunks.",
        ok, skipped, failed, store.count(),
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
