# Seed corpus — Meridian Renewables (fictional)

This is a **synthetic corpus for a fictional company, "Meridian Renewables,"** a
mid-size renewable energy developer. All names, projects, and figures are made
up; nothing here is real or copyrighted, so it's safe to distribute.

The 30 documents are **interconnected** — projects, people, and numbers recur
across files — so that agentic and deep-research questions have real answers
that require pulling from multiple sources. There are also a few deliberate
tensions (e.g. one solar plant's nameplate capacity vs. its derated actual
output) to test whether an agent notices and reconciles conflicting sources.

## Contents (10 / 10 / 10)

**PDFs** — FY2023 annual report, investor overview, three project fact sheets
(Redhawk, Sagebrush, Mesa Verde), health & safety policy, interconnection tech
memo, environmental summary, PPA summary, board minutes.

**Word docs** — employee handbook excerpt, project development procedure, two
O&M reports (Redhawk, Coral Bay), risk register, EPC evaluation, incident
report, org & roles, permitting status, community engagement plan.

**Spreadsheets** — portfolio master list, FY21-23 financials, monthly
generation, O&M cost tracker, development budget, safety incident log, PPA
pricing, headcount, capex tracker, REC inventory.

## Ingest

```bash
make seed        # or: python -m scripts.seed
```

Idempotent and resumable — see the top-level README. Users can add more docs at
runtime through the chat UI.

## A few example questions to try

- "What was Meridian's revenue and EBITDA margin in 2023?" (spreadsheet math)
- "Which projects are still in development, and what's blocking Saltflat Solar?"
  (cross-document: pipeline sheet + permitting memo + board minutes)
- "Why did Coral Bay Solar underperform in 2023?" (derate: O&M report vs.
  generation data vs. annual-report footnote — sources appear to conflict)
- "Who is accountable for safety, and how did the 2023 incident affect the
  numbers?" (policy + incident report + safety log)
- "What is Meridian's home address?" (no-answer case — not in the corpus)
