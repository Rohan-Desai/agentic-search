# Agentic Search — High-Level Plan

## Goal

Build an agent that researches uploaded documents deliberately, answers only from evidence, and clearly explains uncertainty.

> The model makes semantic decisions; application code enforces scope, limits, and validity.

## Responsibilities

| The model decides | The application enforces |
|---|---|
| Meaning and ambiguity | Authorized document scope |
| Whether to decompose | Tool, time, and context budgets |
| Search wording and follow-ups | Argument and result limits |
| Which evidence matters | Evidence identity and deduplication |
| Whether sources conflict | Grounding and citation validation |
| When evidence seems sufficient | Guaranteed termination |

## Agent Flow

```text
Resolve intent → Define requirements → Search → Evaluate evidence
                                      ↑              ↓
                                      └── Refine if needed
                                                     ↓
                                  Answer / partial / clarify / not found
```

## 1. Understand the Question

- Preserve both the original question and the agent’s interpretation.
- Use conversation history to resolve references such as “last year.”
- Ask one focused question only when ambiguity materially changes the answer.
- Decompose broad questions into the smallest useful requirement checklist.
- Keep simple lookups simple.

| Requirement status | Meaning |
|---|---|
| Unsearched | No targeted attempt yet |
| Weak | Related text exists but does not support an answer |
| Supported | Direct evidence exists |
| Conflicting | Material sources disagree |
| Not found | Sensible searches found no support |

## 2. Search Deliberately

- Start with the entity, timeframe, and relationship in the question.
- Reformulate using terminology discovered in retrieved documents.
- Broaden queries that are too specific; narrow noisy results by entity, date, or document.
- Search for missing requirements instead of repeating the original query.
- Inspect surrounding chunks before relying on an isolated passage.
- Stop when consecutive searches add no useful evidence.

Progress means strengthening coverage or resolving a conflict—not merely retrieving more chunks.

## 3. Keep Answers Grounded

> Every important factual claim must trace to evidence retrieved during this request.

- Store accepted passages in a structured evidence ledger with stable IDs.
- Preserve document, chunk, location, query, text, and similarity metadata.
- Map each material claim to the evidence IDs that support it.
- Generate the final answer from accepted evidence only.
- Cite only evidence actually used, with a short supporting snippet.
- Treat similarity scores as retrieval diagnostics, never factual confidence.
- Allow calculations only when inputs, units, periods, and sources are traceable.
- Exclude unsupported speculation.

## 4. Handle Difficult Outcomes

| Situation | Behavior |
|---|---|
| Complete evidence | Return a concise grounded answer |
| Partial evidence | Answer supported portions and identify gaps |
| Material ambiguity | Ask one focused clarification |
| No relevant evidence | Say it was not found in the uploaded documents |
| Source says “unknown” | Report that as a grounded answer |
| Conflicting sources | Reconcile scope/date/units or present both |
| Budget exhausted | Return supported partial findings |
| System failure | Return a safe error, never “no answer” |

## 5. Expose a Small Toolset

| Tool | Purpose |
|---|---|
| `search_evidence` | Broad or document-filtered retrieval |
| `inspect_evidence_context` | Read bounded neighboring chunks |
| `list_documents` | Discover the available corpus |
| `calculate` | Perform safe arithmetic from sourced values |

Tools return structured results. They never expose raw Chroma, embeddings, secrets, unrestricted files, network access, or arbitrary code.

## 6. Enforce Safety and Control

- Effective scope is the intersection of user-authorized and agent-requested documents.
- Uploaded text is untrusted evidence, never an instruction.
- Clamp tool arguments and distinguish empty results from system failures.
- Limit turns, searches, evidence, context, no-progress steps, and elapsed time.
- Retry only transient failures with bounded backoff.
- Show concise operational traces, not private chain-of-thought.

## 7. Validate Before Returning

1. Every material claim has supporting evidence.
2. Every citation exists in the current request’s ledger.
3. Dates, entities, units, and calculations are consistent.
4. Missing information and unresolved conflicts are disclosed.
5. Response flags match the actual outcome.
6. No outside facts were introduced.

Run structural checks every time; add semantic verification only for high-risk numerical, causal, comparative, or conflicting answers.

## 8. Engineer for Clarity

- Keep public API contracts stable and use typed internal research models.
- Isolate query, scope, requirements, attempts, evidence, and budgets per request.
- Separate API, orchestration, tools, validation, storage, and providers.
- Use a small error taxonomy and catch failures at meaningful boundaries.
- Test deterministic behavior without OpenAI and maintain behavioral evaluations.
- Reserve multi-agent planning and synthesis for deep research.

## Delivery Priorities

| Priority | Scope |
|---|---|
| Must be excellent | Agent loop, grounding, citations, tools, robustness, tests |
| Should be solid | Typed state, errors, traces, ingestion metadata, API integration |
| Optional | Hybrid search, table tools, verifier, streaming |
| Out of scope | Auth, queues, cloud deployment, generic agent framework |

## Success Criteria

The agent searches deliberately, adapts when evidence is weak, stops for a clear reason, answers every supported part, exposes uncertainty honestly, and makes every important claim traceable to its source.
