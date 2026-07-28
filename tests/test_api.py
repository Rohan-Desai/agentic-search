"""Smoke tests for the API surface (no OpenAI calls)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_agentic_mode_is_stubbed():
    # Agentic mode is intentionally a stub until the candidate implements it.
    # TestClient re-raises server exceptions, so we assert it raises here.
    import pytest

    with pytest.raises(NotImplementedError):
        client.post("/search", json={"query": "hello", "mode": "agentic"})
