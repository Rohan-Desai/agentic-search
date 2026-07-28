"""Search endpoint — the natural-language entry point for all three modes."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.agents.agentic_search import AgenticSearchRuntimeError
from app.core.logging import get_logger
from app.models.schemas import SearchRequest, SearchResponse
from app.services.search_service import handle_search

router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse | JSONResponse:
    try:
        return await handle_search(req)
    except AgenticSearchRuntimeError as exc:
        logger.warning("Agentic search failed with code=%s", exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.public_message,
                "error_code": exc.code,
            },
        )
