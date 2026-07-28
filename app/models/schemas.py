"""Pydantic request/response schemas shared across the API."""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    """The three retrieval modes the candidate must implement."""

    NORMAL = "normal"          # Plain semantic / keyword search over the index.
    AGENTIC = "agentic"        # An agent decides which tools to call and iterates.
    DEEP_RESEARCH = "deep_research"  # Multi-step planning, decomposition, synthesis.


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    UNKNOWN = "unknown"


class IngestedDocument(BaseModel):
    doc_id: str
    filename: str
    doc_type: DocumentType
    num_chunks: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    documents: list[IngestedDocument]
    message: str = "Ingestion complete."


class Citation(BaseModel):
    doc_id: str
    filename: str
    chunk_id: str | None = None
    snippet: str | None = None
    score: float | None = None
    page: int | None = None
    sheet: str | None = None
    section: str | None = None


class ConversationTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query.")
    mode: SearchMode = SearchMode.NORMAL
    top_k: int = Field(default=5, ge=1, le=50)
    doc_ids: list[str] | None = Field(
        default=None, description="Optionally restrict search to specific documents."
    )
    history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Prior turns, oldest first. Enables multi-turn follow-ups.",
    )


class AgentStep(BaseModel):
    """One step in an agent's reasoning trace, surfaced to the UI for transparency."""

    kind: str  # e.g. "tool_call", "tool_result", "thought", "handoff"
    name: str | None = None
    detail: str | None = None


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    steps: list[AgentStep] = Field(
        default_factory=list, description="Reasoning / tool trace for agentic modes."
    )
    # Robustness signals. Agents should set these rather than hallucinating:
    clarification_needed: bool = Field(
        default=False,
        description="True if the query was too ambiguous to answer confidently.",
    )
    answer_found: bool = Field(
        default=True,
        description="False if the documents do not contain the answer.",
    )
    partial: bool = Field(
        default=False,
        description="True when supported findings exist but coverage is incomplete.",
    )
