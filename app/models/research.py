"""Internal state and tool-result models for one agentic search request."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.schemas import ConversationTurn


class AttemptStatus(str, Enum):
    """Outcome of one tool-backed research attempt."""

    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    INVALID = "invalid"
    FAILED = "failed"


class AgentAnswerOutcome(str, Enum):
    """The three user-facing outcomes produced by agentic search."""

    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    CLARIFICATION = "clarification"


class AgentAnswer(BaseModel):
    """Minimal structured output returned by the agent."""

    answer: str = Field(..., min_length=1)
    outcome: AgentAnswerOutcome


class EvidenceLocation(BaseModel):
    """Location needed to retrieve adjacent chunks from a source document."""

    chunk_order: int | None = Field(default=None, ge=0)


class EvidenceDiscovery(BaseModel):
    """One retrieval event that surfaced a passage."""

    query: str = Field(..., min_length=1)
    retrieval_score: float | None = None


class EvidenceCandidate(BaseModel):
    """Passage returned by retrieval before ledger registration."""

    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    retrieval_score: float | None = None
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)


class EvidenceRecord(BaseModel):
    """One canonical retrieved passage and its provenance."""

    evidence_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)
    discoveries: list[EvidenceDiscovery] = Field(..., min_length=1)


class SearchAttempt(BaseModel):
    """A recorded tool action exposed as an agent step in the response."""

    tool_name: str = Field(..., min_length=1)
    query: str | None = None
    requested_doc_ids: list[str] | None = None
    effective_doc_ids: list[str] | None = None
    result_evidence_ids: list[str] = Field(default_factory=list)
    new_evidence_count: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    status: AttemptStatus = AttemptStatus.SUCCEEDED
    error_code: str | None = None


class EvidenceSearchItem(BaseModel):
    """One current-query result returned by structured retrieval."""

    evidence_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    retrieval_score: float | None = None
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)
    is_new: bool


class EvidenceSearchResult(BaseModel):
    """Structured result of one bounded evidence search."""

    status: AttemptStatus
    query: str = Field(..., min_length=1)
    effective_doc_ids: list[str] | None = None
    evidence: list[EvidenceSearchItem] = Field(default_factory=list)
    new_evidence_count: int = Field(default=0, ge=0)
    error_code: str | None = None


class ContextInspectionResult(BaseModel):
    """Structured result of inspecting context around known evidence."""

    status: AttemptStatus
    source_evidence_id: str = Field(..., min_length=1)
    evidence: list[EvidenceSearchItem] = Field(default_factory=list)
    new_evidence_count: int = Field(default=0, ge=0)
    error_code: str | None = None


class DocumentCatalogItem(BaseModel):
    """One document available within the current request's scope."""

    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_count: int = Field(..., ge=1)


class DocumentListResult(BaseModel):
    """Structured result of listing searchable documents."""

    status: AttemptStatus
    documents: list[DocumentCatalogItem] = Field(default_factory=list)
    truncated: bool = False
    error_code: str | None = None


def utc_now() -> datetime:
    """Return an aware UTC timestamp for request timing."""

    return datetime.now(timezone.utc)


class ResearchContext(BaseModel):
    """Mutable application state isolated to one agentic search request."""

    request_id: str = Field(..., min_length=1)
    original_query: str = Field(..., min_length=1)
    history: list[ConversationTurn] = Field(default_factory=list)
    authorized_doc_ids: list[str] | None = None
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    attempts: list[SearchAttempt] = Field(default_factory=list)
    max_turns: int = Field(default=12, ge=1)
    started_at: datetime = Field(default_factory=utc_now)
