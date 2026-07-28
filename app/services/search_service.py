"""Routes an incoming search request to the correct mode implementation."""
from app.agents.agentic_search import run_agentic_search
from app.agents.deep_research import run_deep_research
from app.agents.normal_search import run_normal_search
from app.models.schemas import SearchMode, SearchRequest, SearchResponse


async def handle_search(req: SearchRequest) -> SearchResponse:
    if req.mode == SearchMode.NORMAL:
        return await run_normal_search(req.query, req.top_k, req.doc_ids)
    if req.mode == SearchMode.AGENTIC:
        return await run_agentic_search(req.query, req.top_k, req.doc_ids, req.history)
    if req.mode == SearchMode.DEEP_RESEARCH:
        return await run_deep_research(req.query, req.top_k, req.doc_ids, req.history)
    raise ValueError(f"Unknown search mode: {req.mode}")
