"""Tests for canonical request-scoped evidence storage."""
import pytest

from app.agents.evidence_ledger import (
    EvidenceLedger,
    EvidenceLedgerInvariantError,
)
from app.models.research import (
    EvidenceCandidate,
    EvidenceDiscovery,
    EvidenceRecord,
    ResearchContext,
)


def candidate(
    *,
    chunk_id: str = "doc-1::0",
    text: str = "Coral Bay available capacity was 82 MW.",
    query: str = "Coral Bay capacity",
    score: float = 0.8,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        doc_id="doc-1",
        filename="operations.docx",
        chunk_id=chunk_id,
        text=text,
        query=query,
        retrieval_score=score,
    )


def research_context() -> ResearchContext:
    return ResearchContext(
        request_id="req-1",
        original_query="What was Coral Bay's capacity?",
    )


def test_add_assigns_stable_ids_and_updates_usage():
    context = research_context()
    ledger = EvidenceLedger(context)

    additions = ledger.add_many(
        [
            candidate(),
            candidate(
                chunk_id="doc-1::1",
                text="The plant was temporarily derated.",
            ),
        ]
    )

    assert [item.evidence_id for item in additions] == ["E1", "E2"]
    assert all(item.is_new for item in additions)
    assert len(context.evidence) == 2


def test_duplicate_chunk_reuses_evidence_and_records_new_discovery():
    context = research_context()
    ledger = EvidenceLedger(context)

    first = ledger.add(candidate())
    duplicate = ledger.add(
        candidate(query="available capacity after derating", score=0.92)
    )

    assert duplicate.evidence_id == first.evidence_id
    assert duplicate.is_new is False
    assert duplicate.discovery_added is True
    assert len(context.evidence) == 1
    assert [item.query for item in context.evidence[0].discoveries] == [
        "Coral Bay capacity",
        "available capacity after derating",
    ]


def test_identical_discovery_is_not_recorded_twice():
    context = research_context()
    ledger = EvidenceLedger(context)

    ledger.add(candidate())
    duplicate = ledger.add(candidate())

    assert duplicate.is_new is False
    assert duplicate.discovery_added is False
    assert len(context.evidence[0].discoveries) == 1


def test_existing_evidence_continues_sequential_ids():
    existing = EvidenceRecord(
        evidence_id="E7",
        doc_id="doc-1",
        filename="operations.docx",
        chunk_id="doc-1::0",
        text="Existing evidence.",
        discoveries=[EvidenceDiscovery(query="existing")],
    )
    context = ResearchContext(
        request_id="req-1",
        original_query="Question",
        evidence=[existing],
    )

    addition = EvidenceLedger(context).add(
        candidate(chunk_id="doc-1::1", text="New evidence.")
    )

    assert addition.evidence_id == "E8"
    assert len(context.evidence) == 2


def test_inconsistent_duplicate_source_is_rejected():
    context = research_context()
    ledger = EvidenceLedger(context)
    ledger.add(candidate())

    with pytest.raises(EvidenceLedgerInvariantError):
        ledger.add(candidate(text="The same chunk unexpectedly changed."))
