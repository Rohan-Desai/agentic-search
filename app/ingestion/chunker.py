"""Simple, dependency-free text chunker.

Splits on paragraph boundaries and packs into ~max_chars windows with overlap.
Candidates may swap this for token-aware or semantic chunking.
"""
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    text: str
    order: int


def chunk_text(text: str, doc_id: str, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[Chunk] = []
    buffer = ""
    order = 0

    def flush(buf: str) -> None:
        nonlocal order
        if buf.strip():
            chunks.append(Chunk(chunk_id=f"{doc_id}::{order}", text=buf.strip(), order=order))
            order += 1

    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= max_chars:
            buffer = f"{buffer}\n{para}" if buffer else para
        else:
            flush(buffer)
            tail = buffer[-overlap:] if overlap and buffer else ""
            buffer = f"{tail}\n{para}" if tail else para
    flush(buffer)
    return chunks
