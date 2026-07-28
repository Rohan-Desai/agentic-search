"""MODE 2: Agentic search  --  ★ CANDIDATE IMPLEMENTS THIS ★

Unlike normal search, the agent should decide *for itself* how to retrieve
information: reformulating queries, calling the retrieval tools one or more
times, deciding when it has enough evidence, and synthesizing a grounded,
cited answer.

You have working tools available in app/agents/tools.py:
  - search_documents(query, top_k)
  - search_within_documents(query, doc_ids, top_k)

Suggested approach (not prescriptive):
  1. Build an `Agent` with clear instructions and `tools=RETRIEVAL_TOOLS`.
  2. Let the agent iterate (the SDK Runner handles the tool loop).
  3. Use run_agent() from app.agents.base to run it and capture the trace.
  4. Populate citations from the tool outputs.

You must handle these robustness cases (they are graded, and the eval dataset
includes them):
  - **Ambiguous query**: set `clarification_needed=True` and ask for scope
    rather than guessing.
  - **No answer in the documents**: set `answer_found=False` and say so, rather
    than hallucinating.
  - **Multi-turn**: `history` contains prior turns (oldest first). A follow-up
    like "what about last year?" should resolve against that context.

Evaluation focus:
  - Sensible tool-use decisions (reformulation, iteration, knowing when to stop).
  - Grounded, accurately cited answers.
  - A useful, transparent reasoning trace (SearchResponse.steps).
  - Correct behavior on the robustness cases above.
"""
from __future__ import annotations

from agents import Agent  # noqa: F401 — available for your implementation

from app.agents.base import default_model, run_agent  # noqa: F401
from app.agents.tools import RETRIEVAL_TOOLS  # noqa: F401
from app.models.schemas import ConversationTurn, SearchResponse


async def run_agentic_search(
    query: str,
    top_k: int,
    doc_ids: list[str] | None,
    history: list[ConversationTurn] | None = None,
) -> SearchResponse:
    # ------------------------------------------------------------------
    # TODO(candidate): Implement agentic search.
    #
    # Example skeleton to get you started:
    #
    #   agent = Agent(
    #       name="Agentic Search",
    #       model=default_model(),
    #       instructions="...your prompt...",
    #       tools=RETRIEVAL_TOOLS,
    #   )
    #   answer, steps, citations = await run_agent(agent, query)
    #   return SearchResponse(
    #       query=query, mode=SearchMode.AGENTIC,
    #       answer=answer, citations=citations, steps=steps,
    #       clarification_needed=..., answer_found=...,
    #   )
    # ------------------------------------------------------------------
    raise NotImplementedError("Implement run_agentic_search for the agentic mode.")
