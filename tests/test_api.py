"""Smoke tests for the API surface (no OpenAI calls)."""
from fastapi.testclient import TestClient

from app.agents.agentic_search import AgenticSearchRuntimeError
from app.main import app
from app.models.schemas import SearchMode, SearchResponse

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_agentic_mode_routes_request_without_real_model_call(monkeypatch):
    captured = {}

    async def fake_agentic_search(query, top_k, doc_ids, history):
        captured.update(
            query=query,
            top_k=top_k,
            doc_ids=doc_ids,
            history=history,
        )
        return SearchResponse(
            query=query,
            mode=SearchMode.AGENTIC,
            answer="Grounded answer.",
            answer_found=True,
        )

    monkeypatch.setattr(
        "app.services.search_service.run_agentic_search",
        fake_agentic_search,
    )
    response = client.post(
        "/search",
        json={
            "query": "What is its limit?",
            "mode": "agentic",
            "top_k": 7,
            "doc_ids": ["doc-1"],
            "history": [
                {"role": "user", "content": "Tell me about the policy."}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Grounded answer."
    assert response.json()["mode"] == "agentic"
    assert captured["query"] == "What is its limit?"
    assert captured["top_k"] == 7
    assert captured["doc_ids"] == ["doc-1"]
    assert captured["history"][0].content == "Tell me about the policy."


def test_agentic_runtime_error_returns_safe_structured_http_failure(monkeypatch):
    async def fake_agentic_search(query, top_k, doc_ids, history):
        raise AgenticSearchRuntimeError(
            "research_timeout",
            "Document research timed out. Please try a narrower question.",
            504,
        )

    monkeypatch.setattr(
        "app.services.search_service.run_agentic_search",
        fake_agentic_search,
    )
    response = client.post(
        "/search",
        json={"query": "hello", "mode": "agentic"},
    )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Document research timed out. Please try a narrower question.",
        "error_code": "research_timeout",
    }
    assert "answer_found" not in response.json()
