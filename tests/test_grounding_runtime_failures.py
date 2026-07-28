from app.models.research import (
    AnswerRequirement,
    AttemptStatus,
    RequirementStatus,
    ResearchAgentOutput,
    ResearchContext,
    ResearchOutcome,
    SearchAttempt,
    StopReason,
)
from app.services.grounding_validator import validate_research_output


def test_failed_tool_attempt_cannot_become_not_found() -> None:
    context = ResearchContext(
        request_id="request-1",
        original_query="Question",
        attempts=[
            SearchAttempt(
                tool_name="search_evidence",
                query="question",
                status=AttemptStatus.FAILED,
                error_code="retrieval_failed",
            )
        ],
    )
    output = ResearchAgentOutput(
        resolved_query="Question",
        outcome=ResearchOutcome.NOT_FOUND,
        answer="The documents do not contain an answer.",
        requirements=[
            AnswerRequirement(
                requirement_id="answer",
                description="Find the answer.",
                status=RequirementStatus.NOT_FOUND,
            )
        ],
        missing_requirements=["answer"],
        stop_reason=StopReason.NOT_FOUND,
    )

    validation = validate_research_output(context, output)

    assert validation.valid is False
    assert validation.repair_allowed is False
    assert (
        "context has failed tool attempts: search_evidence"
        in validation.errors
    )
