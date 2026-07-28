# Agentic Search — Implementation Plan

This plan turns the decisions in `SCRATCHPAD.md` into incremental, testable work. Each phase should leave the repository in a working state.

## Guiding Delivery Rules

- Preserve normal search while agentic mode is developed.
- Introduce internal types before complex orchestration.
- Keep external provider calls behind testable boundaries.
- Complete and verify one vertical slice before adding optional extensions.
- Do not begin deep research until agentic mode is grounded and reliable.

## Phase 0 — Establish the Baseline

### Work

1. Pin and document Python 3.11 as the supported development interpreter.
2. Run the current backend tests and frontend build.
3. Record current endpoint behavior for health, upload, normal, agentic, and deep-research modes.
4. Add a tiny local test corpus covering direct, missing, ambiguous, numerical, and conflicting answers.
5. Document known scaffold limitations before changing behavior.

### Exit Gate

- Existing tests pass.
- Frontend builds.
- Normal mode still runs.
- Test documents and expected behaviors are documented.

## Phase 1 — Define Internal Domain Models

### Work

Create typed internal models for:

- `ResearchContext`: request identity, query, history, authorized scope, budgets, and timing.
- `AnswerRequirement`: one material part of the question and its evidence status.
- `EvidenceRecord`: source identity, location, text, score, query, and evaluation status.
- `EvidenceAssessment`: how one passage supports, contradicts, qualifies, or contextualizes a requirement.
- `SearchAttempt`: requested query, scope, results, timing, and progress made.
- `MaterialClaim`: proposed statement with requirement and supporting-evidence IDs.
- `ValidationResult`: structural and semantic validation findings.
- `StopReason`: complete, clarification, not found, no progress, budget, timeout, or error.

Keep these models internal and add conversion functions to the existing `SearchResponse`.

### Tests

- Model validation and serialization.
- Invalid statuses and identifiers are rejected.
- Evidence deduplication by chunk ID.
- Budget counters and stop reasons behave deterministically.

### Exit Gate

- Research state can be constructed, updated, and validated without an OpenAI call.

## Phase 2 — Improve Document and Evidence Metadata

### Work

1. Introduce a document catalog abstraction.
2. Track document ID, filename, type, content hash, ingestion status, and chunk count.
3. Extend chunks with source-location metadata where available:
   - PDF page
   - Spreadsheet sheet
   - Document section or chunk order
4. Add bounded retrieval of neighboring chunks by document and order.
5. Reject or clearly mark empty parsed documents.
6. Make duplicate-ingestion behavior explicit.

### Tests

- Page and sheet metadata survive parsing, storage, and retrieval.
- Neighbor lookup never crosses document boundaries.
- Exact duplicate files are detected.
- Incomplete ingestion is not reported as complete.

### Exit Gate

- A retrieved passage can be traced to a human-readable source location.

## Phase 3 — Build Request-Scoped Tools

### Work

Implement four model-facing tools:

1. `search_evidence`
   - Semantic retrieval with optional document narrowing.
   - Enforce authorized scope.
   - Clamp result count.
   - Deduplicate and register results in the evidence ledger.
2. `inspect_evidence_context`
   - Accept an evidence ID.
   - Retrieve bounded neighboring chunks.
   - Register newly accepted context.
3. `list_documents`
   - Return a concise catalog within authorized scope.
   - Return a typed empty-corpus result when appropriate.
4. `calculate`
   - Support constrained arithmetic operations.
   - Require input values and their source evidence IDs.
   - Reject unsafe or unsupported expressions.

Use the Agents SDK’s request context mechanism or per-request closures; never use mutable global request state.

### Tests

- Tool schemas are clear and bounded.
- User scope cannot be widened by the model.
- Invalid document or evidence IDs return typed errors.
- Duplicate queries and evidence are tracked.
- Calculation inputs retain provenance.
- Tool/provider errors remain distinct from empty results.

### Exit Gate

- All tools work through deterministic tests without running an agent.

## Phase 4 — Implement the Bounded Agent Loop

### Work

1. Create concise, named agent instructions.
2. Treat retrieved document content as untrusted evidence.
3. Resolve conversational references using history.
4. Identify ambiguity and material answer requirements.
5. Allow the agent to choose tools and evidence-driven query reformulations.
6. Track requirement coverage and progress after every tool call.
7. Enforce:
   - Maximum agent turns
   - Maximum search calls
   - Maximum unique evidence
   - Maximum context size
   - Total timeout
   - Consecutive no-progress cutoff
8. Require a structured final output containing:
   - Natural answer
   - Material claims and evidence IDs
   - Answer status
   - Clarification question when needed
   - Missing requirements
   - Unresolved conflicts
   - Stop reason

### Tests

Use a controlled fake model or recorded SDK events to verify:

- A document question invokes retrieval.
- A weak search is reformulated.
- A multi-part question tracks all requirements.
- Repeated searches trigger no-progress stopping.
- Ambiguity produces a clarification response.
- Tool and time budgets force a safe partial result.

### Exit Gate

- Agentic mode completes the full decision loop with structured output and bounded execution.

## Phase 5 — Grounding and Citation Validation

### Work

1. Validate that every cited evidence ID exists in the current ledger.
2. Validate that every material claim has evidence.
3. Build public `Citation` values only from evidence used by accepted claims.
4. Check entities, dates, units, and derived calculations.
5. Detect multiple values attached to the same entity, metric, and period.
6. Require conflicts to be reconciled or disclosed.
7. Add one bounded repair attempt for invalid structured output.
8. Fail safely if repair does not produce valid grounded output.
9. Add conditional semantic verification for high-risk answers.

### Tests

- Invented evidence IDs are rejected.
- Retrieved-but-unused chunks do not become citations.
- Unsupported claims are removed or cause repair.
- Conflicting sources remain visible.
- Derived calculations use cited inputs.
- No-answer wording remains limited to the searched corpus.

### Exit Gate

- Every returned material claim is structurally connected to retrieved evidence.

## Phase 6 — API and Frontend Integration

### Work

1. Convert internal agent results into the existing `SearchResponse`.
2. Preserve `answer_found` and `clarification_needed`.
3. Represent partial status clearly in answer text and internal trace.
4. Replace raw SDK item dumps with concise operational steps.
5. Display source location and supporting snippet with each citation.
6. Show clear states for clarification, no answer, partial answer, and system failure.
7. Preserve multi-turn history accurately.
8. Add document selection only if it can be enforced end to end.

### Tests

- API contract remains compatible with the frontend.
- Agent exceptions are translated into safe HTTP responses.
- Clarification and no-answer are successful API responses, not server errors.
- Frontend build and core interaction tests pass.

### Exit Gate

- Upload → agentic question → grounded answer → citations works through the UI.

## Phase 7 — Error Handling and Observability

### Work

Define meaningful failures for:

- Empty corpus
- Unsupported or corrupt document
- Parsing failure
- Embedding failure
- Retrieval failure
- Invalid tool input
- Agent execution failure
- Invalid agent output
- Budget exhaustion
- Timeout

Add:

- Request IDs.
- Structured operational logging.
- Sanitized tool traces.
- Per-stage timing.
- Tool-call and evidence counts.
- Stop reason.
- Bounded retries for transient provider errors.

Never log API keys, full documents, or private reasoning.

### Exit Gate

- Every expected failure has a predictable user response and useful internal log.

## Phase 8 — Behavioral Evaluation Suite

### Work

Create representative cases for:

- Direct lookup
- Terminology mismatch and reformulation
- Multi-part coverage
- Multi-turn follow-up
- Material ambiguity
- No relevant answer
- Partial answer
- Conflicting sources
- Numerical derivation
- Document-scope enforcement
- Duplicate evidence
- Tool failure
- Prompt injection
- Budget exhaustion

For each case, record expected:

- Outcome status
- Required or forbidden tool behavior
- Expected supporting documents
- Required disclosures
- Citation properties

Prefer behavioral assertions over exact wording.

### Exit Gate

- Deterministic tests pass.
- Behavioral eval results are recorded.
- A small real-model smoke run demonstrates the intended flow.

## Phase 9 — Optional Improvements

Evaluate in this order:

1. Exact keyword fallback for identifiers, numbers, and phrases.
2. Hybrid retrieval or reranking.
3. Better page, sheet, and section citations.
4. Table-aware spreadsheet querying.
5. Conditional semantic claim verifier.
6. Streaming operational trace.

Only add an extension if it improves a measured failure case without obscuring the core design.

## Phase 10 — Deep Research

Begin only after agentic mode passes its grounding and robustness gates.

Potential flow:

```text
Plan → research independent requirements → evidence-driven follow-ups
     → conflict analysis → grounded synthesis → validation
```

Reuse the evidence ledger, tools, error taxonomy, and validation layer. Introduce planner/researcher/synthesizer separation only where it provides observable value.

## Phase 11 — Final Documentation and Delivery

### README

- Accurate prerequisites and Python version.
- Installation and environment configuration.
- Seed/upload instructions.
- Backend and frontend commands.
- Test and evaluation commands.
- Troubleshooting and known limitations.

### NOTES

- Architecture and request flow.
- Controlled-autonomy rationale.
- Search and stopping policy.
- Grounding and citations.
- Tool selection and rejected alternatives.
- Ambiguity, no-answer, partial, and conflict behavior.
- Testing evidence.
- Tradeoffs and deferred improvements.
- Reproducible example questions.

### Final Gate

- Clean installation succeeds.
- Backend tests and frontend build pass.
- Agentic mode works end to end.
- Expected robustness cases are demonstrated.
- Documentation matches actual behavior.
- Deferred work is stated honestly.
