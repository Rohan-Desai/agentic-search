"""Deterministic tests for hybrid retrieval ranking primitives."""

import pytest

from app.services.vector_store import (
    StoredChunk,
    _keyword_ranking,
    _reciprocal_rank_fusion,
    _tokenize,
)


def chunk(
    chunk_id: str,
    *,
    filename: str,
    text: str,
) -> StoredChunk:
    return StoredChunk(
        doc_id=chunk_id.split("::")[0],
        filename=filename,
        chunk_id=chunk_id,
        text=text,
        order=0,
    )


def test_tokenize_is_case_insensitive_and_splits_punctuation() -> None:
    assert _tokenize("Sagebrush_Wind: LOTO-2023") == [
        "sagebrush",
        "wind",
        "loto",
        "2023",
    ]


def test_keyword_ranking_uses_exact_text_and_filename_terms() -> None:
    chunks = [
        chunk(
            "policy::0",
            filename="Health_and_Safety_Policy.pdf",
            text="General safety responsibilities.",
        ),
        chunk(
            "incident::0",
            filename="Incident_Report_Sagebrush_Aug2023.docx",
            text="Corrective actions included LOTO retraining.",
        ),
    ]

    ranking = _keyword_ranking(
        "Sagebrush incident corrective actions",
        chunks,
    )

    assert ranking[0] == "incident::0"


def test_keyword_ranking_returns_empty_when_no_terms_match() -> None:
    chunks = [
        chunk(
            "policy::0",
            filename="policy.pdf",
            text="Safety responsibilities.",
        )
    ]

    assert _keyword_ranking("coffee supplier", chunks) == []


def test_rrf_rewards_chunks_ranked_by_both_methods() -> None:
    scores = _reciprocal_rank_fusion(
        [
            ["semantic-only", "shared"],
            ["shared", "keyword-only"],
        ]
    )

    assert scores["shared"] > scores["semantic-only"]
    assert scores["shared"] > scores["keyword-only"]
    assert scores["shared"] <= 1.0


def test_rrf_ignores_duplicate_ids_within_one_ranking() -> None:
    scores = _reciprocal_rank_fusion([["E1", "E1", "E2"]])

    assert scores["E1"] == pytest.approx(1.0)
    assert scores["E2"] < scores["E1"]
