# Palladion working memory

Updated 2026-10-17. Navigation aid only; user/vision/source/ADRs retain authority.

## Stable facts

- Repository root `C:/palladion`; system root `palladion/`; branch `main`, existing
  upstream `origin/main`. Initial commit `9b167a2a3fa61147d7104ed28d2f1a6bede1975c`.
- User's vision is [blueprint v0.2](../vision/palladion-blueprint-v2.md), 18 sections,
  1,784 physical lines. Read in full for this setup. Its 74-file tree and code sketches
  are plans/examples, not generated application code.
- Palladion is an evidence-first agent harness for integrity, insufficient-evidence
  recognition, continuity and self-challenge. Initial domain is synthetic support/payment
  investigation; no UI or real payment action. Four read tools and bounded investigation.
- Planned stack: Python 3.11+, FastAPI, SQLite canonical registry/memory, Qdrant dense/BM25,
  optional Neo4j source graph, safe JSON policy evaluator, read-only mock adapters.
  No runtime dependencies, models or versions have been selected/installed by this task.
- Evidence authority belongs to authenticated immutable sources, valid executed policy
  traces and scoped observations. Model/critic/search/graph/memory are not new authority.
- User validity for reported facts differs from owner-defined observation freshness.
- Every development subagent: **GPT 6 Luna High**. Eventual runtime model is undecided.
- Canonical development folder is this folder; exactly one working memory. `baseline/`
  remains reserved and empty for later standard RAG/LangChain/provider comparisons.

## Recovery path

Read root AGENTS → [master plan task protocol](MASTER_DEV_PLAN.md#task-reading-and-execution-protocol)
→ [goal](GOAL.md) → [progress](PROGRESS.md) → relevant [ADRs](ADR_LOG.md),
[risks](RISKS_AND_OPEN_QUESTIONS.md), blueprint sections and [gates](TESTING_GATES.md)
→ live owning code/tests. [Project map](PROJECT_MAP.md) distinguishes actual/planned paths.

## Current state and next action

P00 complete: structural CLI checks and seven negative tests passed; independent Luna High
requirements/fresh suite reviews completed with no material findings. Local checkpoint
is the commit containing this record; no remote push. No product implementation or
experiment exists. System phases P01–P08 are PLANNED; X01 is DEFERRED; G-DOC PASS and
all system gates NOT_RUN. Evidence lives in [EVIDENCE_LOG](EVIDENCE_LOG.md).
After verified P00 closeout, the next implementation unit is **P01-T01**: contracts/corpus
foundation with explicit resolution of approval trust model and tooling/model choices.
This setup task does not authorize starting it automatically.

## Open risks to retain

Q01 approval simulation; Q02 tooling/model pins and cost enablement; Q03/Q04 Qdrant BM25/RRF
compatibility and language; Q05 temporal migration/history; Q06 inventory contract;
Q07 owner freshness; Q08 labels/splits/targets/repetitions; Q09 entailment/escalation;
Q10 optional feature value; Q11 future external comparison; Q12 production retention/auth.
No performance, completeness or production-readiness claim has been established.
