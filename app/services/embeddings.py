"""Thin wrapper around the OpenAI embeddings endpoint."""
from openai import OpenAI

from app.core.config import get_settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    resp = _get_client().embeddings.create(model=settings.embedding_model, input=texts)
    return [item.embedding for item in resp.data]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
