# Agentic Document Search — Take-Home Assignment

## The assignment in one sentence

Build a system that lets a user upload documents (PDFs, Word docs, and
spreadsheets) and ask questions about them in natural language through a chat
interface, backed by a Python service that answers using **normal search and
agentic search**.

## What we're actually assessing

We care about **how you design and reason about agents.** Specifically:

- How an agent decides *what to do* — when to search, how to reformulate a
  query, when it has enough evidence, when to stop.
- How you keep answers **grounded in the documents**, and how the system behaves
  when there's no good answer, the question is ambiguous, or sources disagree.
- Your judgment about **tools**: what you expose to the model, and how.
- General engineering craft: clarity, structure, error handling, and a clear
  writeup of your thinking.

We are **not** assessing UI polish, infra, auth, or how many features you can
cram in. A focused, well-reasoned submission beats a sprawling one.

---

## Read this first: the scaffold is optional

This repo ships with a **complete, working reference implementation** of
everything *except* the agentic search mode we want you to build — file parsing,
chunking, embeddings, a vector store, a FastAPI backend, and a React chat UI.
Normal search is fully implemented so the whole thing runs end-to-end the moment
you set an API key. You are provided an API key in the .env file. An example of the .env file is provided in the .env.example file.

**Treat all of this as a starting point, not a constraint.** You are free to:

- Keep the scaffold and just fill in the agentic search mode (the fast path).
- Restructure, rename, or refactor any part of it.
- **Delete the whole thing and start from scratch** if you'd rather build it
  your way.

There is exactly **one hard requirement**: use the **OpenAI Agents SDK**
(`openai-agents`) as your agent framework, calling OpenAI models. Everything
else — web framework, vector store, chunking strategy, project layout, frontend
approach, how many agents you run and how they're wired — is your call. If you
throw the scaffold away, we just ask that the result still does what the
assignment describes (upload docs, chat UI, normal search, and agentic search)
so we can run it.

If you diverge significantly from the scaffold, say so in `NOTES.md` and tell us
why — that reasoning is signal for us, not a mark against you.

---

## The two modes

The reference backend exposes one endpoint, `POST /search`, that takes a
`mode`. You implement the unbuilt agentic mode (wherever it lives in your
design).

### 1. Normal search — ✅ provided as a reference

Straightforward retrieval-augmented answer: embed the query, pull the top-k
chunks from the vector store, and have the model answer from that context with
the retrieved evidence. No agent loop. It's there so the app runs on day one and
so you have a concrete example of the response contract. You can leave it as-is.

### 2. Agentic search — 🔨 you build this

Instead of a single fixed retrieval, an **agent drives the process**. It should
be able to:

- Decide *how* to search and issue tool calls itself.
- Reformulate or narrow the query based on what it gets back.
- Search more than once if the first pass is weak.
- Decide when it has enough to answer, then produce a grounded response.

The agent should reason over the tools it's given rather than following a
hard-coded sequence. Expose whatever tools you think it needs — retrieval tools
are provided, and you're encouraged to add more.

## Behavior we expect from all modes

Keep this practical. We want to see clear judgment, not a production-grade
system. A strong one-day submission should handle these basics:

- **Ambiguous question** — ask a brief clarification question or state the
  interpretation you're using.
- **Answer isn't in the documents** — say that clearly instead of making one up.
- **Follow-up questions** — use the chat history when it is helpful. The
  reference API accepts a `history` field for this.

---

## Extension ideas (optional, do as many or few as you like)

If you have time and want to show more, here are some directions — these are
**ideas, not a menu you must pick from.** Do one, several, none, or something
else entirely that you think is interesting:

- Stream the agent's reasoning/tool trace to the UI live as it runs.
- Richer multi-turn behavior (query rewriting from context, follow-up suggestions).
- Citations or source snippets that show which documents support the answer.
- A non-trivial custom tool — e.g. cross-document comparison, or
  table-aware/computational querying over spreadsheets rather than plain text
  search.
- Confidence signals or source-quality weighting in the answer.
- Caching, batching, or other latency/cost improvements with measurements.
- Anything else that showcases how you think about agents.

Tell us in `NOTES.md` what you added and why.

---

## Deliverables

1. Working **agentic search** implementation.
2. The **chat UI** functioning against both modes (upload → ask → answer). Keep
   or replace the provided React app.
3. A **`NOTES.md`** (aim for 1–2 pages) covering:
   - Your overall design and agentic-search approach — what you built and *why*.
   - How you handle the behaviors listed above.
   - Any place you diverged from the scaffold, and your reasoning.
   - Trade-offs you made and what you'd do with more time.
   - How to run your submission if it differs from the instructions here.
   - A few example questions (and the docs you tried them on) so we can
     reproduce your results.

---


## Running the reference scaffold

### Prerequisites
- Python 3.11+
- Node 18+ (for the React UI)
- An OpenAI API key

### Backend

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set OPENAI_API_KEY

make seed                   # preload the corpus in data/seed_corpus/ (see below)
make run                    # uvicorn on http://localhost:8000  (API docs at /docs)
```

### Preloading documents (the seed corpus)

A fixed set of documents is provided in **`data/seed_corpus/`**. Ingest them
once, before demoing, with `make seed`. This embeds and stores them in the
persistent vector store (`./data/chroma`).

Seeding is **idempotent and resumable**: it skips any file already in the store,
so if the process is killed partway through — or you restart the demo — just run
`make seed` again and it only processes what's missing. Already-ingested
documents survive restarts because the vector store is persisted to disk. Use
`python -m scripts.seed --force` to re-ingest everything from scratch.

Users can still upload more documents at runtime through the chat UI; those
persist to the same store alongside the seeded corpus.

### Frontend (second terminal)

```bash
make install-frontend       # cd frontend && npm install
make frontend               # vite dev server on http://localhost:5173
```

The UI proxies `/documents`, `/search`, and `/health` to the backend on :8000.
Open **http://localhost:5173**, drop in a few documents, and try **Normal
search** — it works immediately. Agentic search returns a "not implemented"
error until you build it.

### Ingest from the CLI (prints the doc_ids)

```bash
python -m scripts.ingest path/to/report.pdf path/to/data.xlsx
```

### Tests

```bash
make test     # pytest — ingestion + API smoke tests (no API key needed)
make lint     # ruff
```

---

## How the reference scaffold is laid out

```
app/
  main.py                  FastAPI app: /documents/upload, /search, /health
  core/                    config (env-based settings), logging
  models/schemas.py        Request/response models: SearchMode, SearchRequest
                           (incl. multi-turn `history`), SearchResponse
                           (incl. steps, clarification_needed, answer_found)
  ingestion/
    parsers.py             PDF / DOCX / XLSX -> text                [reference]
    chunker.py             text -> overlapping chunks               [reference]
  services/
    embeddings.py          OpenAI embeddings wrapper                [reference]
    vector_store.py        Chroma-backed store: add() / search()    [reference]
    ingest_service.py      parse -> chunk -> embed -> store         [reference]
    search_service.py      routes a request to the right mode       [reference]
  agents/
    tools.py               @function_tool retrieval tools for agents  [use / extend]
    base.py                run_agent() helper + trace extraction      [use / extend]
    normal_search.py       Mode 1                                     [reference impl]
    agentic_search.py      Mode 2   ★ YOU BUILD ★
  api/routes/              documents.py, search.py, health.py
frontend/                  React + TypeScript + Vite chat UI          [keep / replace]
  src/
    App.tsx                Chat state, mode tabs, multi-turn history
    components/            Sidebar (upload), Message (answer + trace), Composer
    lib/api.ts             Typed client for the backend
data/
  seed_corpus/             Drop preload documents here → `make seed`  [provided]
  chroma/                  Persistent vector store (created on first ingest)
scripts/
  seed.py                  Idempotent corpus seeding (skips already-ingested)
  ingest.py                CLI ingestion helper (prints doc_ids)
tests/                     Ingestion, API, and seed/idempotency smoke tests
```

### Request flow (reference)

```
Upload:  file → parsers.parse → chunker.chunk_text → embeddings → vector_store.add
Chat:    UI → POST /search {query, mode, history}
             → search_service.handle_search
             → { normal | agentic }
                    ↓ (agentic)
             Agent + tools → vector_store.search → grounded answer
```

### Tools you're given

`app/agents/tools.py` has ready-to-use function tools (decorated with the SDK's
`@function_tool`); pass `RETRIEVAL_TOOLS` to an agent's `tools=`:

- `search_documents(query, top_k)` — hybrid search across everything.
- `search_within_documents(query, doc_ids, top_k)` — scoped hybrid search.

`app/agents/base.py`'s `run_agent(agent, query)` runs an agent to completion and
extracts a basic tool-call trace you can surface in the UI. Add tools and
improve the trace as you see fit.

### A minimal agentic example (OpenAI Agents SDK)

```python
from agents import Agent
from app.agents.base import run_agent, default_model
from app.agents.tools import RETRIEVAL_TOOLS

agent = Agent(
    name="Agentic Search",
    model=default_model(),
    instructions="Search the documents as many times as needed, then answer from the evidence.",
    tools=RETRIEVAL_TOOLS,
)
answer, steps, _ = await run_agent(agent, query)
```

SDK docs: <https://openai.github.io/openai-agents-python/> — see **Agents**,
**function tools**, and **streaming**.

---

## Ground rules

- **Use the OpenAI Agents SDK** for the agent layer, with OpenAI models. This is
  the one fixed requirement.
- If you keep the reference backend, don't change the `POST /search` contract or
  the `add`/`search` interface of the vector store without saying so — the UI
  and tools depend on them. If you rebuild, just keep the app runnable and
  document how.
- Commit incrementally so we can follow your thinking.
- Use whatever libraries and tools you like otherwise.

Good luck — we're looking forward to seeing how you approach it.
