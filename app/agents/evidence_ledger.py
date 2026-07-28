"""Canonical evidence storage for one agentic research request."""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.models.research import (
    EvidenceAssessment,
    EvidenceCandidate,
    EvidenceDiscovery,
    EvidenceRecord,
    EvidenceRelationship,
    ResearchContext,
)

_EVIDENCE_ID = re.compile(r"E(\d+)")


class EvidenceLedgerError(ValueError):
    """Base class for invalid evidence-ledger operations."""


class EvidenceLedgerInvariantError(EvidenceLedgerError):
    """Existing context contains inconsistent canonical evidence."""


class UnknownEvidenceError(EvidenceLedgerError):
    """An operation referenced evidence that is not in this ledger."""


class UnknownRequirementError(EvidenceLedgerError):
    """An operation referenced a requirement that is not in this request."""


class EvidenceAddition(BaseModel):
    """Result of registering one retrieved candidate."""

    evidence_id: str
    is_new: bool
    discovery_added: bool


class EvidenceLedger:
    """Manage canonical evidence and assessments inside one research context.

    A source chunk is canonicalized by ``(doc_id, chunk_id)``. Finding that
    chunk again records another discovery but does not create new evidence or
    count as evidence progress.
    """

    def __init__(self, context: ResearchContext) -> None:
        self.context = context
        self._by_id: dict[str, EvidenceRecord] = {}
        self._id_by_source: dict[tuple[str, str], str] = {}
        self._requirements = {item.requirement_id: item for item in context.requirements}
        self._index_existing_evidence()

    def _index_existing_evidence(self) -> None:
        highest_number = 0
        for record in self.context.evidence:
            if record.evidence_id in self._by_id:
                raise EvidenceLedgerInvariantError(
                    f"Duplicate evidence id: {record.evidence_id}"
                )

            source_key = (record.doc_id, record.chunk_id)
            if source_key in self._id_by_source:
                raise EvidenceLedgerInvariantError(
                    f"Duplicate canonical source: {record.doc_id}/{record.chunk_id}"
                )

            self._by_id[record.evidence_id] = record
            self._id_by_source[source_key] = record.evidence_id
            match = _EVIDENCE_ID.fullmatch(record.evidence_id)
            if match:
                highest_number = max(highest_number, int(match.group(1)))

        self._next_number = highest_number + 1
        self.context.usage.evidence_count = len(self.context.evidence)
        self.context.usage.context_chars = sum(
            len(record.text) for record in self.context.evidence
        )

    def add(self, candidate: EvidenceCandidate) -> EvidenceAddition:
        """Register a candidate, deduplicating repeated source chunks."""

        source_key = (candidate.doc_id, candidate.chunk_id)
        existing_id = self._id_by_source.get(source_key)
        discovery = EvidenceDiscovery(
            query=candidate.query,
            retrieval_score=candidate.retrieval_score,
        )

        if existing_id is not None:
            record = self._by_id[existing_id]
            if record.text != candidate.text or record.filename != candidate.filename:
                raise EvidenceLedgerInvariantError(
                    f"Source changed for canonical evidence {existing_id}"
                )

            discovery_added = discovery not in record.discoveries
            if discovery_added:
                record.discoveries.append(discovery)
            return EvidenceAddition(
                evidence_id=existing_id,
                is_new=False,
                discovery_added=discovery_added,
            )

        evidence_id = self._new_evidence_id()
        record = EvidenceRecord(
            evidence_id=evidence_id,
            doc_id=candidate.doc_id,
            filename=candidate.filename,
            chunk_id=candidate.chunk_id,
            text=candidate.text,
            location=candidate.location,
            discoveries=[discovery],
        )
        self.context.evidence.append(record)
        self._by_id[evidence_id] = record
        self._id_by_source[source_key] = evidence_id
        self.context.usage.evidence_count += 1
        self.context.usage.context_chars += len(record.text)
        return EvidenceAddition(
            evidence_id=evidence_id,
            is_new=True,
            discovery_added=True,
        )

    def add_many(self, candidates: list[EvidenceCandidate]) -> list[EvidenceAddition]:
        """Register candidates in retrieval order."""

        return [self.add(candidate) for candidate in candidates]

    def get(self, evidence_id: str) -> EvidenceRecord:
        """Return canonical evidence or raise a typed lookup error."""

        try:
            return self._by_id[evidence_id]
        except KeyError as exc:
            raise UnknownEvidenceError(f"Unknown evidence id: {evidence_id}") from exc

    def assess(
        self,
        evidence_id: str,
        requirement_id: str,
        relationship: EvidenceRelationship,
        rationale: str | None = None,
    ) -> EvidenceAssessment:
        """Create or replace how evidence relates to one requirement."""

        self.get(evidence_id)
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise UnknownRequirementError(f"Unknown requirement id: {requirement_id}")

        assessment = EvidenceAssessment(
            evidence_id=evidence_id,
            requirement_id=requirement_id,
            relationship=relationship,
            rationale=rationale,
        )
        for index, existing in enumerate(self.context.evidence_assessments):
            if (
                existing.evidence_id == evidence_id
                and existing.requirement_id == requirement_id
            ):
                self.context.evidence_assessments[index] = assessment
                break
        else:
            self.context.evidence_assessments.append(assessment)

        if evidence_id not in requirement.evidence_ids:
            requirement.evidence_ids.append(evidence_id)
        return assessment

    def evidence_for_requirement(self, requirement_id: str) -> list[EvidenceRecord]:
        """Return assessed evidence for one known requirement."""

        if requirement_id not in self._requirements:
            raise UnknownRequirementError(f"Unknown requirement id: {requirement_id}")
        evidence_ids = {
            item.evidence_id
            for item in self.context.evidence_assessments
            if item.requirement_id == requirement_id
        }
        return [record for record in self.context.evidence if record.evidence_id in evidence_ids]

    def _new_evidence_id(self) -> str:
        while f"E{self._next_number}" in self._by_id:
            self._next_number += 1
        evidence_id = f"E{self._next_number}"
        self._next_number += 1
        return evidence_id
