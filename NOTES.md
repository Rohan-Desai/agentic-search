# Implementation Notes

## Approach

I implemented agentic search as one OpenAI Agents SDK agent with three
request-scoped document tools:

- `search_evidence` performs hybrid semantic and BM25 retrieval across all
  authorized documents or a model-selected subset.
- `inspect_evidence_context` retrieves bounded neighboring chunks when an
  isolated result needs context.
- `list_documents` exposes the searchable document catalog without treating the
  catalog itself as evidence.

The Agents SDK provides the decision loop. After each tool result, the model
chooses whether to reformulate, narrow to a document, inspect context, search
again, or answer. Application code does not prescribe a fixed sequence.

Each request owns a `ResearchContext` and `EvidenceLedger`. Successful retrieval
results receive stable IDs such as `E1` and are deduplicated by document and
chunk. The final answer cites those IDs inline. The application verifies that
each cited ID exists in the current ledger and projects it into the existing
`SearchResponse.citations` contract.

The agent's structured output is deliberately small:

- `answer`
- `outcome`: `answered`, `not_found`, or `clarification`

I initially considered explicit requirement graphs and a separate validation
and repair pipeline. Behavioral testing showed that this duplicated model
bookkeeping without proving factual correctness, so I chose the smaller design.

Initial manual evaluation also showed that semantic retrieval could miss exact
filenames, spreadsheet rows, numbers, and rare incident terminology. I added
BM25 keyword ranking over filename plus chunk text and combined it with Chroma's
semantic ranking using Reciprocal Rank Fusion. The model still sees one search
tool; retrieval quality improves without adding another tool-selection decision.

## Required behaviors

The prompt asks the agent to:

- search before returning a factual answer;
- break multi-part questions into separate searches when useful;
- reformulate weak or repetitive searches;
- use document discovery and scoped retrieval when broad search stalls;
- retrieve source inputs for calculations and comparisons;
- ask a focused clarification question when interpretation materially changes
  the answer;
- say exactly what was not found instead of filling gaps with outside knowledge;
- expose unresolved document discrepancies without inventing an explanation;
- stop when evidence is sufficient or further retrieval would repeat results.

Conversation history is included to resolve follow-ups such as “What about
Coral Bay?” Evidence IDs are request-scoped, so old citation markers are removed
from history and factual follow-ups retrieve fresh evidence.

If sources disagree, the agent is instructed to report the discrepancy and
avoid guessing which source is correct. If the documents do not contain an
answer, it returns `not_found`; if ambiguity would materially change the answer,
it returns `clarification` with one focused question.

## Grounding and citations

Only passages returned by the request-scoped tools enter the evidence ledger.
Inline forms such as `[E1][E2]` and `[E1, E2]` are supported. Citations preserve
the filename, document ID, chunk ID, snippet, and best retrieval score.

Retrieval score is a normalized hybrid rank signal, not confidence that a claim
is true. The implementation guarantees that a citation came from an authorized
document retrieved during the current request. It does not claim to
deterministically prove that the cited text entails every sentence.

## Scope and controls

- The user-selected document scope cannot be widened by the model.
- The API request controls retrieval `top_k`.
- The SDK run is capped at 12 turns.
- Context inspection is limited to nearby chunks in the same source.
- Document text is presented as evidence, not executable instructions.

## Scaffold changes and tradeoffs

I retained the provided FastAPI API, ingestion pipeline, Chroma store, response
contract, and React UI. The main additions are the agentic-search
implementation, request-scoped retrieval and evidence services, and tests. I
also changed the shared `VectorStore.search()` implementation from semantic-only
retrieval to hybrid semantic and BM25 retrieval. This benefits normal and
agentic modes while preserving the provided `add()`/`search()` interface.

I chose one agent rather than planner, researcher, and validator agents. For
this corpus, a single SDK tool loop is easier to understand and test while
still allowing genuine model-directed reformulation and repeated search.

The current BM25 implementation loads scoped chunk text from Chroma for each
search. That is simple and appropriate for this small corpus, but a large
production collection would need a persistent lexical index or a store with
native hybrid retrieval. The agent can also narrow to an unhelpful document
subset, so improved retrieval does not remove model-level tool judgment.

Model-generated arithmetic and interpretation can still be imperfect. A
table-aware query tool or calculator would improve numerical reliability, but
I left these out to keep the submission focused.

The operational trace shows observable tool activity rather than private model
reasoning. Provider and vector-store telemetry warnings are not customized in
this implementation.

## Running

The standard README instructions are unchanged. In the backend terminal:

```bash
make seed
make run
```

In a second terminal:

```bash
make install-frontend
make frontend
```

Open `http://localhost:5173` and select **Agentic** mode.

## Reproducible examples

These were tested against the included seed corpus:

| Question | Expected source documents |
|---|---|
| “What caused Meridian’s 2023 lost-time incident, and what corrective actions were taken?” | `Incident_Report_Sagebrush_Aug2023.docx` |
| “Compare Sagebrush Wind’s 2023 electricity generation with its reported RECs generated.” | `Monthly_Generation_2023.xlsx`, `REC_Inventory_2023.xlsx` |
| “Which operating project had the lowest 2023 O&M cost per MWh? Show all four calculations.” | `OM_Cost_Tracker_2023.xlsx`, `Monthly_Generation_2023.xlsx` |
| “Does Saltflat Solar’s reported G4 stage agree with Meridian’s formal stage-gate procedure and current permitting status?” | `Development_Budget_Pipeline.xlsx`, `Project_Development_Procedure.docx`, `Permitting_Status_Q4_2023.docx` |
| “What brand of coffee is served in Meridian’s Boulder office?” | No supporting document; expected behavior is `not_found` |

For a follow-up test, ask “Summarize Redhawk Solar’s PPA terms,” then “What
about Coral Bay?”, then “Which has the higher energy price?” The relevant
sources are `PPA_Summary_Redhawk_Solar.pdf` and `PPA_Pricing_Schedule.xlsx`.
