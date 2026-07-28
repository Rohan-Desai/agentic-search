"""MODE 3: Deep research  --  ★ CANDIDATE IMPLEMENTS THIS ★

The most sophisticated mode. A single tool-using agent is usually not enough.
We expect a multi-step pipeline, for example:

  1. PLAN     -- decompose the question into sub-questions / research angles.
  2. RESEARCH -- investigate each sub-question (retrieval + reasoning), possibly
                 with a dedicated sub-agent or agent-as-tool / handoffs. At least
                 one sub-question should be able to trigger a FOLLOW-UP query
                 based on what an earlier step found (not a fixed linear script).
  3. SYNTHESIZE -- combine findings into a coherent, cited report, noting gaps
                 or conflicting evidence across documents.

The OpenAI Agents SDK supports patterns that fit well here -- handoffs,
agents-as-tools, and orchestrator agents. How you compose them is up to you;
that design decision is a core part of what we're evaluating. You must justify
your choice of orchestration pattern in NOTES.md.

Robustness expectations also apply here: handle conflicting sources explicitly
in the synthesis, and set `answer_found` / `clarification_needed` appropriately.
`history` is available for multi-turn follow-ups.

Evaluation focus:
  - Quality of decomposition and planning.
  - Genuine multi-step orchestration (NOT one big prompt), including at least
    one follow-up query driven by an intermediate finding.
  - Synthesis quality: structure, grounding, citations, handling of gaps and
    conflicting evidence.
  - Transparency of the process via SearchResponse.steps.
"""
from __future__ import annotations

from app.models.schemas import ConversationTurn, SearchResponse


async def run_deep_research(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
) -> SearchResponse:
    # ------------------------------------------------------------------
    # TODO(candidate): Implement a multi-step deep-research pipeline.
    # Design the orchestration yourself. Aim for planning -> research ->
    # synthesis, surface the process in `steps`, and justify the design in
    # NOTES.md.
    # ------------------------------------------------------------------
    raise NotImplementedError("Implement run_deep_research for the deep-research mode.")
