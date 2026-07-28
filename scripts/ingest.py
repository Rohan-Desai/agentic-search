"""CLI helper: ingest one or more local files without going through the API.

Usage:  python -m scripts.ingest path/to/file.pdf path/to/data.xlsx
"""
import sys
from pathlib import Path

from app.services.ingest_service import ingest_file


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ingest <file> [<file> ...]")
        raise SystemExit(1)
    for arg in sys.argv[1:]:
        doc = ingest_file(Path(arg))
        print(f"Ingested {doc.filename}: {doc.num_chunks} chunks (doc_id={doc.doc_id})")


if __name__ == "__main__":
    main()
