# Implementation Notes

## 1. Design goals and decisions

I aimed to build a practical document-search agent rather than a production
research platform. The important goals were genuine model-directed retrieval,
grounded answers, sensible uncertainty handling, and an implementation I could
clearly explain and test.

### Agent control

The agent must decide how to search, whether to reformulate, when evidence is
sufficient, and when to stop.

| Approach considered | Benefit | Cost |
|---|---|---|
| Hard-coded search workflow | Predictable and easy to test | Not genuinely agentic |
| Multiple planner/researcher/validator agents | Specialized responsibilities | More cost, state, and failure modes |
| One tool-using agent | Simple, but still model-directed | Less deterministic |

I chose one OpenAI Agents SDK agent. The SDK owns the tool loop, while the
instructions define expectations for multi-part searches, reformulation,
completeness, ambiguity, and stopping. The application enforces boundaries but
does not prescribe a fixed research sequence.

### Grounding

| Approach considered | Benefit | Limitation |
|---|---|---|
| Put retrieved text directly in one prompt | Minimal implementation | Weak provenance and no iterative retrieval |
| Request-scoped evidence IDs | Traceable, deduplicated citations | Does not prove semantic entailment |
| Separate validator agent | Another check on the answer | Still probabilistic; adds complexity |
| Quote-backed claims | Stronger passage provenance | Does not prove correct interpretation |

I chose a request-scoped `EvidenceLedger`. Every retrieved chunk receives an ID
such as `E1`; final citations must resolve to evidence collected during that
request. This proves that a cited passage exists and was retrieved, but not that
every model interpretation is logically correct. I document that limitation
rather than presenting retrieval score as factual confidence.

### Tools

Too few tools restrict the agent, while too many create unnecessary decisions.
I exposed three focused actions:

| Tool | Purpose |
|---|---|
| `search_evidence` | Search all authorized documents or a model-selected subset |
| `list_documents` | Discover available filenames and document IDs |
| `inspect_evidence_context` | Read nearby chunks when a result needs qualification |

The model supplies only tool arguments such as a query or document IDs. Private
request state, document authorization, storage access, and ledger updates remain
in application code.

### Retrieval

Semantic search handles paraphrases but sometimes missed filenames, numbers,
spreadsheet rows, and rare incident terminology during manual QA.

| Strategy | Strength | Weakness |
|---|---|---|
| Semantic retrieval | Meaning and paraphrases | Exact terms can be missed |
| BM25 keyword retrieval | Names, numbers, rare terms | Weak on paraphrases |
| Hybrid retrieval | Combines both signals | More retrieval work |

I combine Chroma semantic rankings with BM25 rankings over filename and chunk
text using Reciprocal Rank Fusion. This changed the shared
`VectorStore.search()` implementation, so normal and agentic modes both benefit
without changing its public interface.

I initially modeled requirement graphs, claims, assessments, validation state,
and detailed budgets. Those structures did not drive the final runtime and did
not guarantee correctness, so I removed them. The smaller design better matches
the assignment and is easier to reason about.

## 2. Final implementation

```text
POST /search
     |
     v
Search service --> One Agents SDK agent
                         |
          +--------------+--------------+
          |              |              |
   list_documents  search_evidence  inspect_context
                         |
                  Hybrid retrieval
                 /                \
          Chroma semantic        BM25
                 \                /
              Reciprocal Rank Fusion
                         |
                  Evidence ledger
                         |
                 Answer + citations
```

For each request:

1. The API receives the query, mode, document scope, `top_k`, and history.
2. `run_agentic_search()` creates a `ResearchContext` and an
   `AgentToolContext` containing its ledger.
3. The SDK runner lets the model call tools or finish.
4. Tool code enforces scope, retrieves passages, registers them as `E1`, `E2`,
   and so on, and returns those passages to the model.
5. The model can reformulate, narrow, inspect context, or search again.
6. The final structured output is `answer` plus `outcome`: `answered`,
   `not_found`, or `clarification`.
7. Application code resolves cited evidence IDs into the existing public
   `Citation` objects and exposes tool attempts as UI steps.

The prompt requires a current-request search before a factual answer. It asks
the model to search separately for missing parts, retrieve source inputs for
calculations, ask one focused question when ambiguity materially changes the
answer, and state exactly what was not found. When documents conflict, it
reports the discrepancy without guessing which source is correct. Historical
citation markers are removed from follow-up context because evidence IDs are
request-scoped; factual follow-ups search again for fresh evidence.

| The application guarantees | It does not guarantee |
|---|---|
| Cited evidence exists and was retrieved | Every interpretation is correct |
| The agent cannot widen document scope | A citation entails every sentence |
| Repeated chunks reuse one evidence ID | No conflicting passage exists elsewhere |
| The run stops after at most 12 SDK turns | Model-generated arithmetic is perfect |

I retained the supplied FastAPI API, ingestion pipeline, Chroma store, response
contract, and React UI. I added the agentic loop, request-scoped tools,
retrieval service, evidence ledger, hybrid ranking, and focused tests.

### Running

Backend:

```bash
pip install -r requirements.txt
make seed
make run
```

Second terminal:

```bash
make install-frontend
make frontend
```

Open `http://localhost:5173` and select **Agentic** mode.

## 3. Limitations, future work, and examples

The current agent remains probabilistic. BM25 loads scoped chunks from Chroma
for each search, citations prove provenance rather than semantic entailment,
spreadsheets are retrieved as text, and arithmetic is model-generated.

With more time, I would first build a repeatable evaluation set measuring
document recall, answer correctness, citation support, latency, and tool calls.
I would then use those measurements to prioritize:

1. persistent lexical search and candidate reranking;
2. table-aware spreadsheet retrieval with row and cell provenance;
3. a calculator for derived answers;
4. claim-to-evidence validation, optionally including verified quotations; and
5. measured caching and tighter time/tool budgets.

### Reproducible examples

| Question | Expected source documents |
|---|---|
| What caused Meridian’s 2023 lost-time incident, and what corrective actions were taken? | `Incident_Report_Sagebrush_Aug2023.docx` |
| Compare Sagebrush Wind’s 2023 generation with its reported RECs. | `Monthly_Generation_2023.xlsx`, `REC_Inventory_2023.xlsx` |
| Which operating project had the lowest 2023 O&M cost per MWh? Show all four calculations. | `OM_Cost_Tracker_2023.xlsx`, `Monthly_Generation_2023.xlsx` |
| Does Saltflat Solar’s G4 stage agree with the procedure and permitting status? | `Development_Budget_Pipeline.xlsx`, `Project_Development_Procedure.docx`, `Permitting_Status_Q4_2023.docx` |
| What brand of coffee is served in Meridian’s Boulder office? | No supporting document; expected outcome is `not_found` |

For a follow-up test, ask “Summarize Redhawk Solar’s PPA terms,” then “What
about Coral Bay?”, then “Which has the higher energy price?” Expected sources
are `PPA_Summary_Redhawk_Solar.pdf` and `PPA_Pricing_Schedule.xlsx`.
