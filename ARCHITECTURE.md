# Agentic Search — Architecture

## System Context

```mermaid
flowchart LR
    U[User] --> UI[React Chat UI]
    UI -->|Upload files| API[FastAPI]
    UI -->|Question, mode, history| API
    API --> ING[Ingestion Service]
    API --> SEARCH[Search Service]
    ING --> PARSE[Document Parsers]
    PARSE --> CHUNK[Metadata-Aware Chunker]
    CHUNK --> EMBED[OpenAI Embeddings]
    EMBED --> STORE[(Chroma Vector Store)]
    ING --> CATALOG[(Document Catalog)]
    SEARCH --> NORMAL[Normal RAG]
    SEARCH --> AGENT[Agentic Search]
    SEARCH --> DEEP[Deep Research]
    NORMAL --> STORE
    NORMAL --> OPENAI[OpenAI Models]
    AGENT --> OPENAI
    AGENT --> TOOLS[Research Tools]
    TOOLS --> STORE
    TOOLS --> CATALOG
    DEEP --> OPENAI
    DEEP --> TOOLS
```

## Backend Boundaries

```mermaid
flowchart TB
    subgraph Delivery["Delivery Layer"]
        ROUTES[API Routes]
        PUBLIC[Public Request/Response Models]
    end

    subgraph Application["Application Layer"]
        ROUTER[Search Mode Router]
        ORCH[Agentic Orchestrator]
        DR[Deep-Research Orchestrator]
        NORMAL[Normal Search]
    end

    subgraph Domain["Research Domain"]
        CTX[Research Context]
        REQS[Answer Requirements]
        LEDGER[Evidence Ledger]
        CLAIMS[Material Claims]
        VALIDATE[Grounding Validator]
        BUDGET[Budgets and Stop Policy]
    end

    subgraph Capabilities["Model-Facing Capabilities"]
        SEARCH_TOOL[search_evidence]
        CONTEXT_TOOL[inspect_evidence_context]
        LIST_TOOL[list_documents]
        CALC_TOOL[calculate]
    end

    subgraph Infrastructure["Infrastructure"]
        VECTOR[Vector Store]
        DOCS[Document Catalog]
        PARSERS[Parsers and Chunking]
        MODELS[OpenAI Models and Embeddings]
    end

    ROUTES --> PUBLIC
    ROUTES --> ROUTER
    ROUTER --> NORMAL
    ROUTER --> ORCH
    ROUTER --> DR
    ORCH --> CTX
    CTX --> REQS
    CTX --> LEDGER
    CTX --> BUDGET
    ORCH --> SEARCH_TOOL
    ORCH --> CONTEXT_TOOL
    ORCH --> LIST_TOOL
    ORCH --> CALC_TOOL
    SEARCH_TOOL --> VECTOR
    CONTEXT_TOOL --> VECTOR
    LIST_TOOL --> DOCS
    LEDGER --> CLAIMS
    CLAIMS --> VALIDATE
    VALIDATE --> PUBLIC
    NORMAL --> VECTOR
    NORMAL --> MODELS
    ORCH --> MODELS
    DR --> MODELS
    VECTOR --> MODELS
    PARSERS --> VECTOR
    PARSERS --> DOCS
```

## Upload and Ingestion Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as React UI
    participant API as Upload API
    participant Ingest as Ingestion Service
    participant Parser as Parser/Chunker
    participant Embed as OpenAI Embeddings
    participant Store as Chroma
    participant Catalog as Document Catalog

    User->>UI: Select files
    UI->>API: POST /documents/upload
    API->>Ingest: Ingest each file
    Ingest->>Ingest: Validate type and content hash
    Ingest->>Catalog: Mark document processing
    Ingest->>Parser: Extract text and source locations
    Parser-->>Ingest: Ordered metadata-aware chunks
    Ingest->>Embed: Embed chunk texts
    Embed-->>Ingest: Embedding vectors
    Ingest->>Store: Store chunks, metadata, embeddings
    Ingest->>Catalog: Mark document complete
    Ingest-->>API: Document result or typed failure
    API-->>UI: Successful and failed files
```

## Agentic Search Request

```mermaid
sequenceDiagram
    actor User
    participant UI as React UI
    participant API as Search API
    participant Orch as Agentic Orchestrator
    participant Agent as OpenAI Agent
    participant Tools as Research Tools
    participant Ledger as Evidence Ledger
    participant Validator as Grounding Validator

    User->>UI: Ask question
    UI->>API: query + history + selected scope
    API->>Orch: Start agentic search
    Orch->>Orch: Create request-scoped context and budgets
    Orch->>Agent: Question, history, policies, tool schemas
    Agent->>Agent: Resolve intent and answer requirements

    loop Until complete, no progress, or budget reached
        Agent->>Tools: Request bounded research action
        Tools->>Tools: Enforce scope, arguments, and budget
        Tools-->>Ledger: Register structured evidence/results
        Tools-->>Agent: Structured result or typed error
        Agent->>Agent: Evaluate coverage and choose next action
    end

    Agent-->>Orch: Structured answer, claims, evidence IDs, outcome
    Orch->>Validator: Validate structure and grounding

    alt Valid
        Validator-->>Orch: Accepted result
    else Repairable
        Validator-->>Agent: Specific validation failures
        Agent-->>Orch: One repaired structured result
    else Unsafe or still invalid
        Validator-->>Orch: Safe failure
    end

    Orch-->>API: SearchResponse with citations and steps
    API-->>UI: Answer / clarification / partial / no answer
```

## Agent Decision Loop

```mermaid
flowchart TD
    START[Receive question and history] --> RESOLVE[Resolve intent]
    RESOLVE --> AMBIG{Material ambiguity?}
    AMBIG -->|Yes| DISCOVER{Can corpus discovery resolve it safely?}
    DISCOVER -->|No| CLARIFY[Ask one focused clarification]
    DISCOVER -->|Yes| PLAN
    AMBIG -->|No| PLAN[Define minimal answer requirements]
    PLAN --> SEARCH[Choose a research tool and query]
    SEARCH --> RESULTS{Useful evidence returned?}
    RESULTS -->|No| ALT{Meaningfully different search remains?}
    ALT -->|Yes| SEARCH
    ALT -->|No| GAP[Mark requirement not found]
    RESULTS -->|Yes| LEDGER[Grade and register evidence]
    LEDGER --> CONFLICT{Material conflict?}
    CONFLICT -->|Yes| RECONCILE[Search dates, scope, units, definitions, authority]
    RECONCILE --> LEDGER
    CONFLICT -->|No| COVERAGE{All requirements resolved?}
    GAP --> COVERAGE
    COVERAGE -->|No| PROGRESS{Budget and progress remain?}
    PROGRESS -->|Yes| SEARCH
    PROGRESS -->|No| PARTIAL[Prepare supported partial outcome]
    COVERAGE -->|Yes| SYNTH[Build claims from accepted evidence]
    SYNTH --> VALIDATE[Validate claims, citations, flags, and calculations]
    VALIDATE --> VALID{Valid?}
    VALID -->|Yes| ANSWER[Return grounded answer]
    VALID -->|Repairable once| SYNTH
    VALID -->|No| SAFE[Return safe system failure]
    CLARIFY --> END[SearchResponse]
    PARTIAL --> END
    ANSWER --> END
    SAFE --> END
```

## Request-Scoped Research State

```mermaid
classDiagram
    class ResearchContext {
        request_id
        original_query
        resolved_query
        history
        authorized_doc_ids
        started_at
        stop_reason
    }

    class ToolBudget {
        max_turns
        max_searches
        max_evidence
        max_context_chars
        timeout_seconds
        no_progress_limit
    }

    class AnswerRequirement {
        requirement_id
        description
        status
        evidence_ids
    }

    class SearchAttempt {
        query
        requested_scope
        effective_scope
        tool_name
        result_ids
        new_evidence_count
        duration
        status
    }

    class EvidenceRecord {
        evidence_id
        doc_id
        filename
        chunk_id
        location
        text
        evidence_status
    }

    class EvidenceDiscovery {
        query
        retrieval_score
    }

    class EvidenceAssessment {
        evidence_id
        requirement_id
        relationship
        rationale
    }

    class MaterialClaim {
        claim_id
        text
        requirement_ids
        evidence_ids
        claim_type
    }

    class ValidationResult {
        valid
        errors
        warnings
        repair_allowed
    }

    ResearchContext "1" *-- "1" ToolBudget
    ResearchContext "1" *-- "*" AnswerRequirement
    ResearchContext "1" *-- "*" SearchAttempt
    ResearchContext "1" *-- "*" EvidenceRecord
    ResearchContext "1" *-- "*" EvidenceAssessment
    ResearchContext "1" *-- "*" MaterialClaim
    ResearchContext "1" *-- "0..1" ValidationResult
    EvidenceAssessment "*" --> "1" AnswerRequirement
    EvidenceAssessment "*" --> "1" EvidenceRecord
    EvidenceRecord "1" *-- "*" EvidenceDiscovery
    MaterialClaim "*" --> "*" EvidenceRecord
    MaterialClaim "*" --> "*" AnswerRequirement
```

## Trust and Authority Boundaries

```mermaid
flowchart LR
    USER[User request and selected scope] --> POLICY[Application policy]
    DOC[Uploaded document text<br/>Untrusted evidence] --> MODEL[Agent]
    POLICY -->|Maximum allowed scope| TOOLS[Bounded tools]
    MODEL -->|May narrow scope| TOOLS
    TOOLS -->|Validated structured results| MODEL
    MODEL --> OUTPUT[Proposed claims and citations]
    OUTPUT --> VALIDATOR[Application validation]
    VALIDATOR --> RESPONSE[Public response]

    SECRETS[API keys and internal services] -. never exposed .-> POLICY
    RAW[Filesystem, raw Chroma, arbitrary code] -. not model-accessible .-> TOOLS
```

The model can choose research actions, but it cannot override document scope, tool limits, permissions, output validation, or access hidden infrastructure.

## Outcome Model

| Internal outcome | Public behavior |
|---|---|
| Complete | Grounded answer with used citations |
| Partial | Supported answer plus explicit missing portions |
| Clarification | Focused question with `clarification_needed=True` |
| Not found | Corpus-limited explanation with `answer_found=False` |
| Conflict | Reconciled explanation or transparent presentation of both sources |
| Budget stop | Supported partial result with stop reason in trace |
| System failure | Safe error response; never presented as no evidence |

## Design Constraints

- The model owns semantic judgment; application code owns authority and limits.
- Tools return structured evidence, not final answers.
- Public API contracts remain stable while internal models evolve.
- Every material claim must be traceable to current-request evidence.
- Document text is data, never trusted instruction.
- Normal search remains a fixed RAG baseline.
- Multi-agent orchestration is reserved for deep research.
