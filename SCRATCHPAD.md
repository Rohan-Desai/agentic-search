# Agentic Search Scratchpad

Working design notes and decisions. Keep this concise; detailed implementation choices come later.

## 1. How the Agent Decides What to Do

### Core Principle

> Let the model make semantic decisions; let the application enforce operational boundaries.

The model decides what the question means, what evidence is missing, and how to search. The application enforces budgets, grounding, progress checks, and valid outputs.

### Chosen Direction

Use a **single tool-using research agent inside a bounded evidence-coverage loop** for agentic mode.

```text
Resolve intent → Define answer requirements → Search → Evaluate evidence
                                            ↑              ↓
                                            └── Refine if needed
                                                           ↓
                                              Answer / clarify / no answer
```

| Decision | Reasoning |
|---|---|
| Use hybrid controlled autonomy | More adaptive than a fixed pipeline, more reliable than a fully autonomous agent |
| Require retrieval for claims about documents | Prevents answers based only on model memory |
| Decompose only multi-part or broad questions | Preserves completeness without overcomplicating simple lookups |
| Track explicit answer requirements | Makes “enough evidence” and answer completeness measurable |
| Reformulate based on retrieved evidence | Corpus terminology is more useful than blindly generated synonyms |
| Track unique chunks and search progress | Prevents repeated searches from creating false confidence |
| Use semantic and mechanical stop rules | Gives the agent judgment while guaranteeing termination |
| Keep multi-agent orchestration for deep research | Standard agentic mode should remain focused and understandable |

### Evidence-Coverage Model

Each material part of the question should have a state:

| State | Meaning |
|---|---|
| `unsearched` | No targeted retrieval attempted |
| `weak_evidence` | Related text exists but does not directly support an answer |
| `supported` | Direct, relevant evidence exists |
| `conflicting` | Sources materially disagree |
| `not_found` | Reasonable searches found no supporting evidence |

Evidence is sufficient when every material requirement is supported or transparently marked as unavailable, and unresolved conflicts are disclosed.

### Search and Reformulation Rules

| Situation | Preferred next action |
|---|---|
| Initial document question | Search using the entity, timeframe, and requested relationship |
| No or weak evidence | Simplify or broaden the query; remove assumptions |
| One answer component is missing | Search specifically for that component |
| Results reveal corpus terminology | Re-query using the discovered terminology |
| Results are too broad | Narrow by entity, date, concept, or document IDs |
| Sources disagree | Search for dates, units, definitions, scope, and source authority |
| Repeated searches add no new evidence | Stop and report the gap |

### Stop Conditions

| Outcome | Condition |
|---|---|
| Answer | All material requirements have supporting evidence |
| Clarify | Material ambiguity remains after using history and available scope |
| No answer | Sensible query variants produce no direct support |
| Partial answer | Some requirements are supported; remaining gaps are explicitly disclosed |
| Forced stop | Tool/iteration/time budget is reached; return only supported findings |

Mechanical guardrails: maximum iterations/tool calls, timeout, duplicate-query detection, context limit, and a no-progress cutoff.

### Main Concerns and Mitigations

| Concern | Mitigation |
|---|---|
| Agent answers without searching | Enforce retrieval before document-based factual answers |
| Agent mistakes semantic similarity for proof | Evaluate direct support; do not treat vector score as confidence |
| Multi-part questions are only partly answered | Maintain an answer-requirements checklist and audit before finalizing |
| Agent repeats equivalent searches | Track query similarity, retrieved chunk IDs, and new evidence gained |
| Retrieval failure is mistaken for corpus absence | Try a small number of meaningfully different searches and use careful wording |
| Sources conflict | Reconcile scope/date/units where possible; otherwise disclose both |
| Agent searches forever | Enforce budgets and stop after consecutive no-progress steps |
| Architecture becomes overengineered | Keep one primary agent for agentic mode; reserve orchestration for deep research |

### Open Questions

- Exact structure used to represent the research plan and evidence ledger.
- Whether intent resolution is a separate model call or part of the main agent loop.
- How strict retrieval-score filtering should be.
- Whether complex answers receive a second model-based validation pass.
- Exact iteration, tool-call, and no-progress budgets.

## 2. Keeping Answers Grounded

### Core Principle

> Every important factual claim must trace back to evidence actually retrieved from the documents.

A citation is not decoration: the cited passage must genuinely support the claim. Vector similarity helps find candidates, but it is **not** proof or confidence.

### Chosen Direction

Use a **structured evidence ledger with claim-to-evidence validation**.

```text
Retrieve passages → Grade evidence → Build answer from accepted evidence
                                              ↓
                               Validate claims and citations
                                              ↓
                         Answer / partial / clarify / not found
```

| Decision | Reasoning |
|---|---|
| Keep structured evidence records | Preserves source, location, query, and relevance instead of relying on raw tool text |
| Generate from accepted evidence only | Reduces unsupported facts and irrelevant context |
| Map material claims to evidence IDs | Makes grounding inspectable and testable |
| Cite only evidence used in the answer | Avoids decorative citations and citation overload |
| Validate output every time | Ensures cited chunks exist, were retrieved, and match the response flags |
| Use extra semantic verification selectively | Adds protection for numerical, causal, comparative, or conflicting answers without slowing every lookup |

### Evidence Ledger

Each accepted passage should retain:

| Field | Purpose |
|---|---|
| Evidence ID | Stable reference used by claims |
| Document, chunk, and location | Traceability back to the source |
| Passage text | Exact evidence available to the answer generator |
| Search query | Explains how it was discovered |
| Answer requirement | Shows which part of the question it supports |
| Evidence quality | Candidate, direct, contextual, weak, or rejected |
| Requirement relationship | Supports, contradicts, qualifies, or provides context |

Preserve page, sheet, or section metadata during ingestion where possible. Show users the filename, location, and a short supporting snippet.

### Grounding Rules

| Situation | Required behavior |
|---|---|
| Direct fact | Cite the passage that states it |
| Derived fact or calculation | Cite the input facts, verify units/timeframes, and label it as derived |
| Interpretation | Use cautious wording and cite the evidence supporting the interpretation |
| Unsupported speculation | Exclude it |
| Only part of the question is supported | Answer that part and clearly state what was not found |
| No relevant evidence after sensible searches | Say it was not found **in the uploaded documents** |
| Documents explicitly say something is unknown | Treat that as a grounded answer |

### Ambiguity and Disagreement

| Case | Response |
|---|---|
| History or document scope resolves ambiguity | Continue using the resolved interpretation |
| Different interpretations would materially change the answer | Ask one focused clarification question |
| Sources use different dates, units, or scopes | Explain the distinction |
| One source is more authoritative for the claim | Prefer it and explain why when relevant |
| Conflict cannot be resolved | Present both claims and state what remains unclear |

Do not resolve conflicts by counting how many documents repeat each claim. Prefer claim-specific authority, recency, scope, and precision.

### Validation

Always check:

- Every material claim has supporting evidence.
- Every citation points to evidence retrieved during this run.
- Dates, entities, units, and calculations are consistent.
- Missing information and unresolved conflicts are disclosed.
- `answer_found` and `clarification_needed` match the actual response.
- The answer does not introduce outside facts.

Use deterministic checks for structure. Add a model-based support check only for higher-risk answers.

### Main Concerns and Mitigations

| Concern | Mitigation |
|---|---|
| Model fills evidence gaps from memory | Restrict final synthesis to accepted evidence |
| Citation mentions the topic but does not support the claim | Validate claim-to-evidence support |
| Weak retrieval is mistaken for an answer | Grade direct support separately from similarity score |
| Every retrieved chunk is shown as a citation | Cite only passages actually used |
| “Not retrieved” is stated as “does not exist” | Use corpus-limited wording and try meaningfully different searches first |
| Conflicting numbers are silently combined | Compare date, unit, definition, scope, and authority |
| Validation becomes expensive | Always run structural checks; reserve semantic verification for complex answers |

### Open Questions

- Exact schema for evidence records and material claims.
- How page, sheet, and section metadata will flow through ingestion.
- Rules for deciding when semantic verification is required.
- Whether to extend the API beyond `answer_found` with `complete`, `partial`, and `not_found`.

## 3. Tool Design

### Core Principle

> Expose a small set of meaningful research actions; keep storage details, safety rules, and permissions in application code.

Tools should let the agent find and inspect evidence—not access Chroma, embeddings, files, or arbitrary code directly.

### Chosen Toolset

| Tool | Purpose |
|---|---|
| `search_evidence` | Broad or targeted document search with optional document scope |
| `inspect_evidence_context` | Read nearby chunks to recover headings, caveats, and table context |
| `list_documents` | Understand the available corpus and resolve document names |
| `calculate` | Safely compute totals, differences, percentages, and ratios from sourced values |

Keep this to roughly four distinct tools. Add specialized capabilities only when they enable a genuinely different action.

### How Tools Should Work

```text
Agent requests an action
        ↓
Application validates scope, arguments, and budget
        ↓
Tool performs one bounded operation
        ↓
Structured result enters the evidence ledger
```

| Decision | Reasoning |
|---|---|
| Combine broad and document-scoped search | Avoid two overlapping tools that differ only by a filter |
| Use structured results | Prevent fragile parsing and preserve citation metadata |
| Give results stable evidence IDs | Simplifies context inspection, citations, and validation |
| Use request-scoped tool context | Keeps user scope, budgets, and evidence isolated without burdening the model |
| Allow a small model-requested `top_k` range | Supports adaptive searches while controlling noise and cost |
| Treat scores as retrieval similarity only | High similarity does not prove that a passage supports a claim |
| Keep reasoning outside tools | Tools perform actions; the agent evaluates evidence and chooses what comes next |

### Application-Enforced Boundaries

The model may narrow scope, but it cannot widen user-selected scope:

```text
effective scope = user-authorized documents ∩ agent-requested documents
```

Always enforce:

- Valid, bounded arguments and result sizes.
- Tool-call, evidence, context, and time budgets.
- Duplicate-query and duplicate-evidence detection.
- Clear separation between no results, invalid input, and system failure.
- Bounded retries for transient infrastructure failures only.
- Sanitized operational traces for debugging.

### Tool Output

Search results should include:

| Field | Why |
|---|---|
| Evidence ID | Stable reference for later actions |
| Document and chunk IDs | Source traceability |
| Filename and source location | Human-verifiable citations |
| Passage text | Evidence available to the model |
| Retrieval score | Search diagnostic, not confidence |
| Query used | Explains how the evidence was found |

### Security

Uploaded documents are untrusted evidence and may contain prompt-injection text such as “ignore previous instructions.”

- Never treat document text as agent instructions.
- Do not expose secrets, unrestricted files, network access, or code execution.
- Enforce permissions and budgets outside the model.
- Keep tools narrow enough that malicious document text cannot grant new capabilities.

### Deferred Tools

| Capability | Decision |
|---|---|
| Exact/keyword or hybrid search | Useful next retrieval improvement |
| Table-aware spreadsheet querying | Strong extension after the core agent works |
| Whole-document retrieval | Avoid; too large and imprecise |
| Document summarization | Better suited to deep research; summaries are indirect evidence |
| Compare/conflict/citation tools | Keep these in agent reasoning and validation |
| Researcher agent as a tool | Reserve for deep-research orchestration |
| Raw Chroma, embeddings, filesystem, or Python | Do not expose |

### Main Concerns and Mitigations

| Concern | Mitigation |
|---|---|
| Too many overlapping tools confuse the agent | Keep a small set with distinct purposes |
| Model requests huge result sets | Clamp `top_k` and total evidence |
| Isolated chunks are misleading | Let the agent inspect bounded surrounding context |
| Tool strings are hard to parse into citations | Return structured evidence records |
| Agent searches outside requested documents | Enforce scope in application code |
| Infrastructure errors look like “no answer” | Return typed error statuses |
| Documents manipulate the agent | Treat content as untrusted and minimize capabilities |

### Open Questions

- Whether initial search supports semantic and exact modes separately or uses hybrid retrieval.
- Exact request-scoped context mechanism supported by the Agents SDK.
- Calculator input schema and how source evidence IDs accompany values.
- Initial per-tool and total research budgets.

## 4. Engineering Craft

### Core Principle

> Keep the agent's semantic freedom inside a small, typed, request-scoped architecture with explicit boundaries and predictable failure behavior.

Build the parts that demonstrate agent judgment thoroughly; keep everything else intentionally simple.

### Structure

```text
API contract
    ↓
Search-mode orchestration
    ↓
Request-scoped research context
    ↓
Tools → evidence ledger → grounding validation
    ↓
Storage and OpenAI services
```

| Component | Owns |
|---|---|
| API routes | HTTP validation and responses |
| Search service | Mode selection |
| Agent orchestrator | Research lifecycle and stop outcome |
| Research context | Per-request scope, evidence, attempts, and budgets |
| Tools | One bounded external action each |
| Grounding validator | Claims, citations, calculations, and response flags |
| Storage/provider services | Chroma, parsing, embeddings, and model calls |

Keep public API models stable. Use separate typed internal models for evidence, requirements, attempts, claims, validation, and stop reasons.

### Code Decisions

| Decision | Reasoning |
|---|---|
| Separate by responsibility, not file size | Avoid one giant agent file without creating dozens of wrappers |
| Make outer control flow explicit in code | Model choices remain understandable and bounded |
| Keep prompts named and centralized | Easier to review, test, and document |
| Use request-scoped state | Prevent hidden global state and cross-request leakage |
| Prefer enums and typed models over loose dictionaries | Catch invalid states early and communicate intent |
| Avoid premature frameworks | We need one provider, one store, and three known modes |

### Error Handling

Distinguish valid outcomes from system failures:

| Outcome | Handling |
|---|---|
| Empty corpus | Ask the user to upload or seed documents |
| No relevant evidence | Valid response with `answer_found=False` |
| Ambiguous question | Valid clarification response |
| Partial research | Return supported findings and disclose gaps |
| Invalid agent output | Validate, repair or retry once, then fail safely |
| Tool/provider timeout | Bounded retry for transient errors |
| Budget exhausted | Stop cleanly; never invent missing findings |
| Unexpected bug | Log details with request ID; return a safe generic error |

Catch errors at meaningful boundaries—parsing, embeddings, retrieval, tools, agent execution, output validation, and the API. Never turn a real system failure into “no answer.”

### Reliability

- Set per-call and total request timeouts.
- Enforce tool, evidence, and context budgets.
- Retry only transient failures with bounded backoff.
- Keep per-request state isolated.
- Do not report ingestion success until all chunks are stored.
- Prefer content hashes over filenames for duplicate detection.
- Keep blocking work simple for the demo; document scaling limitations instead of adding a job queue.

### Testing

| Layer | Focus |
|---|---|
| Unit tests | Evidence deduplication, budgets, citations, calculations, scope, errors |
| Integration tests | Parse → chunk → store → tool result; API with mocked agent/model |
| Contract tests | API schemas, tool schemas, frontend/backend compatibility |
| Behavioral evals | Search decisions, reformulation, grounding, ambiguity, conflicts, stopping |
| Real-model smoke tests | A small optional suite for end-to-end confidence |

Prefer behavioral assertions over exact answer text. Examples: correct source cited, required search occurred, every claim has evidence, and document scope was respected.

### Documentation

| Document | Audience and purpose |
|---|---|
| `README.md` | Install, run, use, test, and troubleshoot |
| `SCRATCHPAD.md` | Compact evolving decisions |
| `NOTES.md` | Final evaluator-facing architecture, reasoning, tradeoffs, examples, and limitations |
| Code docstrings/comments | Non-obvious contracts and why decisions exist |

Be explicit about limitations and deferred work. Clear scope judgment is stronger than unsupported “production-ready” claims.

### Scope Priorities

| Priority | Work |
|---|---|
| Must be excellent | Agent loop, grounding, citations, tools, robustness cases, critical tests |
| Should be solid | Typed state, errors, traces, API integration, ingestion correctness |
| Optional | Hybrid search, calculator, better locations, table tools, verifier, streaming |
| Out of scope | Auth, distributed queues, cloud deployment, enterprise telemetry, generic agent framework |

### Main Concerns and Mitigations

| Concern | Mitigation |
|---|---|
| Agent logic becomes one tangled file | Separate orchestration, state, tools, prompts, and validation |
| Internal changes break the UI | Keep public and internal models separate |
| Exceptions are swallowed or misleading | Use a small typed error taxonomy and boundary translation |
| Agent tests are brittle | Test behavior and evidence properties, not exact wording |
| Model calls make every test slow and costly | Mock providers for most tests; keep a small real-model suite |
| Scope expands beyond the assignment | Prioritize evaluated behaviors and document deliberate omissions |

### Open Questions

- Final internal module and model layout.
- Which optional improvements fit after the core behavior is verified.
- Exact timeout, retry, and partial-response policies.
- Shape and size of the behavioral evaluation dataset.
