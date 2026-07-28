"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health, search
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="Agentic Document Search",
    description="Natural-language search over PDFs, Word docs, and spreadsheets.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(search.router)


@app.get("/")
async def root() -> dict[str, str]:
    # The UI is a separate React app (see frontend/). Run it with `npm run dev`;
    # it proxies API calls here. Interactive API docs live at /docs.
    return {
        "service": "agentic-document-search",
        "docs": "/docs",
        "frontend": "run `npm run dev` in ./frontend (http://localhost:5173)",
    }
