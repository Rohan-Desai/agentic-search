"""Shared helpers for building and running agents.

`run_agent` wraps `Runner.run` and extracts a reasoning/tool trace from the
result so the API can surface it to the UI (see SearchResponse.steps).
"""
from __future__ import annotations

from agents import Agent, Runner

from app.core.config import get_settings
from app.models.schemas import AgentStep, Citation


async def run_agent(agent: Agent, query: str) -> tuple[str, list[AgentStep], list[Citation]]:
    """Run an agent to completion and return (answer, steps, citations).

    The steps/citations extraction below is intentionally basic. Improving it —
    e.g. parsing tool outputs into structured Citation objects — is part of the
    assignment for the agentic and deep-research modes.
    """
    result = await Runner.run(agent, query)

    steps: list[AgentStep] = []
    for item in result.new_items:
        item_type = getattr(item, "type", "")
        if item_type == "tool_call_item":
            raw = getattr(item, "raw_item", None)
            steps.append(
                AgentStep(
                    kind="tool_call",
                    name=getattr(raw, "name", None),
                    detail=str(getattr(raw, "arguments", "")),
                )
            )
        elif item_type == "tool_call_output_item":
            steps.append(AgentStep(kind="tool_result", detail=str(getattr(item, "output", ""))))
        elif item_type == "handoff_call_item":
            steps.append(AgentStep(kind="handoff", detail="handoff requested"))

    # TODO(candidate): parse tool outputs into structured Citation objects.
    citations: list[Citation] = []

    return result.final_output, steps, citations


def default_model() -> str:
    return get_settings().agent_model
