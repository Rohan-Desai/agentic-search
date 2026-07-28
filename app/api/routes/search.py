"""Search endpoint — the natural-language entry point for all three modes."""
from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.services.search_service import handle_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    return await handle_search(req)
