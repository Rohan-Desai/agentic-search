"""Internal models for one agentic research request.

These models are intentionally separate from the public API schemas. They
describe how research is tracked internally and can evolve without breaking
the frontend contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.schemas import ConversationTurn


class RequirementStatus(str, Enum):
    """How well the evidence ledger covers one part of the question."""

    UNSEARCHED = "unsearched"
    WEAK = "weak"
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    NOT_FOUND = "not_found"


class EvidenceStatus(str, Enum):
    """Intrinsic quality of a retrieved passage."""

    CANDIDATE = "candidate"
    DIRECT = "direct"
    CONTEXTUAL = "contextual"
    WEAK = "weak"
    REJECTED = "rejected"


class EvidenceRelationship(str, Enum):
    """How one evidence record relates to one answer requirement."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXT = "context"


class AttemptStatus(str, Enum):
    """Outcome of one tool-backed research attempt."""

    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    INVALID = "invalid"
    FAILED = "failed"


class StopReason(str, Enum):
    """Why the research loop ended."""

    COMPLETE = "complete"
    CLARIFICATION = "clarification"
    NOT_FOUND = "not_found"
    NO_PROGRESS = "no_progress"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"
    ERROR = "error"


class ResearchOutcome(str, Enum):
    """User-facing shape of the research result."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    CLARIFICATION = "clarification"
    NOT_FOUND = "not_found"


class ClaimType(str, Enum):
    """How a material claim relates to its supporting evidence."""

    DIRECT = "direct"
    DERIVED = "derived"
    INTERPRETATION = "interpretation"


class EvidenceLocation(BaseModel):
    """Human-readable location inside a source document."""

    page: int | None = Field(default=None, ge=1)
    sheet: str | None = None
    section: str | None = None
    chunk_order: int | None = Field(default=None, ge=0)


class EvidenceDiscovery(BaseModel):
    """One retrieval event that surfaced a passage."""

    query: str = Field(..., min_length=1)
    retrieval_score: float | None = None


class EvidenceCandidate(BaseModel):
    """Structured passage returned by retrieval before ledger registration."""

    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    retrieval_score: float | None = None
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)


class EvidenceRecord(BaseModel):
    """One retrieved passage and its provenance."""

    evidence_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)
    status: EvidenceStatus = EvidenceStatus.CANDIDATE
    discoveries: list[EvidenceDiscovery] = Field(..., min_length=1)


class AnswerRequirement(BaseModel):
    """One material part of a question that needs an evidence-backed answer."""

    requirement_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    status: RequirementStatus = RequirementStatus.UNSEARCHED
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceAssessment(BaseModel):
    """A semantic relationship between evidence and an answer requirement."""

    evidence_id: str = Field(..., min_length=1)
    requirement_id: str = Field(..., min_length=1)
    relationship: EvidenceRelationship
    rationale: str | None = None


class SearchAttempt(BaseModel):
    """A recorded tool action and whether it advanced the research."""

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


class MaterialClaim(BaseModel):
    """A factual statement proposed for the final answer."""

    claim_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    requirement_ids: list[str] = Field(..., min_length=1)
    evidence_ids: list[str] = Field(..., min_length=1)
    claim_type: ClaimType = ClaimType.DIRECT


class ValidationResult(BaseModel):
    """Result of checking a proposed answer against collected evidence."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    repair_allowed: bool = False


class ResearchAgentOutput(BaseModel):
    """Structured proposal returned by the research agent.

    This is not yet a publishable API response. A later validation layer must
    verify its references and grounding before the answer reaches a user.
    """

    resolved_query: str = Field(..., min_length=1)
    outcome: ResearchOutcome
    answer: str = Field(..., min_length=1)
    requirements: list[AnswerRequirement] = Field(default_factory=list)
    evidence_assessments: list[EvidenceAssessment] = Field(default_factory=list)
    claims: list[MaterialClaim] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    stop_reason: StopReason


class ResearchBudget(BaseModel):
    """Configured upper bounds for one agentic search."""

    max_turns: int = Field(default=8, ge=1)
    max_tool_calls: int = Field(default=8, ge=1)
    max_searches: int = Field(default=5, ge=1)
    max_evidence: int = Field(default=30, ge=1)
    max_context_chars: int = Field(default=30_000, ge=1)
    timeout_seconds: float = Field(default=60.0, gt=0)
    no_progress_limit: int = Field(default=2, ge=1)


class ResearchUsage(BaseModel):
    """Resources consumed so far by one agentic search."""

    turns: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    searches: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    context_chars: int = Field(default=0, ge=0)
    consecutive_no_progress: int = Field(default=0, ge=0)


def utc_now() -> datetime:
    """Return an aware UTC timestamp for request timing."""

    return datetime.now(timezone.utc)


class ResearchContext(BaseModel):
    """All mutable research state isolated to one incoming search request."""

    request_id: str = Field(..., min_length=1)
    original_query: str = Field(..., min_length=1)
    resolved_query: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list)
    authorized_doc_ids: list[str] | None = None
    requirements: list[AnswerRequirement] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    evidence_assessments: list[EvidenceAssessment] = Field(default_factory=list)
    attempts: list[SearchAttempt] = Field(default_factory=list)
    claims: list[MaterialClaim] = Field(default_factory=list)
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    usage: ResearchUsage = Field(default_factory=ResearchUsage)
    started_at: datetime = Field(default_factory=utc_now)
    stop_reason: StopReason | None = None
    validation: ValidationResult | None = None
