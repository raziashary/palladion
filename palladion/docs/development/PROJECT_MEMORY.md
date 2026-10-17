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
  User selected uv and real Groq `qwen/qwen3.8-27b`; package choices are delegated after GO.
  No app dependencies are installed by this task; exact pins/embedding model remain to verify.
- Evidence authority belongs to authenticated immutable sources, valid executed policy
  traces and scoped observations. Model/critic/search/graph/memory are not new authority.
- User validity for reported facts differs from owner-defined observation freshness.
- Every development subagent: **GPT 6 Luna High**. Every phase requires one pre-phase
  adversary and, after tests/gates, one post-phase work auditor. Current whole-suite
  restructure also needs coordinator and auditor checks against the entire blueprint.
- Canonical development folder is this folder; exactly one working memory. `baseline/`
  remains reserved and empty for later standard RAG/LangChain/provider comparisons.

## Recovery path

Read root AGENTS → [master plan task protocol](MASTER_DEV_PLAN.md#task-reading-and-execution-protocol)
→ [goal](GOAL.md) → [progress](PROGRESS.md) → relevant [ADRs](ADR_LOG.md),
[risks](RISKS_AND_OPEN_QUESTIONS.md), blueprint sections and [gates](TESTING_GATES.md)
→ live owning code/tests. [Project map](PROJECT_MAP.md) distinguishes actual/planned paths.

## Current state and next action

Earlier verified checkpoints `26015fd`/`bc44932`; current P00-T05 records all accepted
answers, structured editable ADRs and uv/Groq/review changes (ADR-0011–ADR-0023).
G-DOC PASS at E-DOC-003: 23 structured ADRs, 93 cards, 18 negative controls, coordinator
and single post-auditor full-vision reviews complete with all findings resolved. Nine
documentation children checked, 84 system children planned. Current docs checkpoint is
the commit containing this record. No active implementation; WAIT_FOR_GO.
All Q01–Q12 recommendation directions answered; verification and deferred work remain.
No product code/research result exists; system gates NOT_RUN, X01 DEFERRED.

After docs closure: **WAIT_FOR_GO**, including no installation, venv creation, provider
call, implementation or push. User may manage uv setup independently. Intended app venv:
`C:/palladion/palladion/.venv` via uv venv; later baseline has a separate environment.
Credential file stays at repository-root `.env`, ignored and unread by this task; never
copy it into the app/agents. At initial check root `.gitignore` was user-owned/untracked;
uv was not found on shell PATH. Recheck actual state after GO; don't assume installation.

## Open risks to retain

Accepted directions and remaining evidence are separate: Q03/Q04 compatibility/language,
Q05 audit fixtures, Q07 configured synthetic freshness values, Q08 labels/calibration,
Q09 actual rubric/escalation assignment, Q10 optional-feature value; Q06/Q11/Q12 external
inventory/comparators/real deployment remain deferred. No unanswered recommendation is
silently promoted into empirical success.
No performance, completeness or production-readiness claim has been established.
