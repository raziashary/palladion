# Palladion working memory

Updated 2026-10-18. Navigation aid only; user/vision/source/ADRs retain authority.

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
  P01/P02 dependencies and embedding/retrieval identities are installed/locked and verified.
- Evidence authority belongs to authenticated immutable sources, valid executed policy
  traces and scoped observations. Model/critic/search/graph/memory are not new authority.
- User validity for reported facts differs from owner-defined observation freshness.
- Every development subagent: **GPT 6 Luna Medium**. Every phase requires one pre-phase
  adversary and, after tests/gates, one post-phase work auditor. Current whole-suite
  restructure also needs coordinator and auditor checks against the entire blueprint.
  Both future reviewer roles directly read the complete blueprint and follow MASTER_DEV_PLAN
  “Blueprint review contract for both reviewers”; task-card-only review is insufficient.
- Canonical development folder is this folder; exactly one working memory. `baseline/`
  remains reserved and empty for later standard RAG/LangChain/provider comparisons.

## Recovery path

Read root AGENTS → [master plan task protocol](MASTER_DEV_PLAN.md#task-reading-and-execution-protocol)
→ [goal](GOAL.md) → [progress](PROGRESS.md) → relevant [ADRs](ADR_LOG.md),
[risks](RISKS_AND_OPEN_QUESTIONS.md), blueprint sections and [gates](TESTING_GATES.md)
→ live owning code/tests. [Project map](PROJECT_MAP.md) distinguishes actual/planned paths.

## Current state and next action

P02 DONE from published aa4b439; E-P02-001, ADR-0025/0026. All15 children verified:
canonical ingestion/catalog, approved additive schema v3, actual dense/BM25 Qdrant,
exact-ID/canonical/ACL retrieval, authenticated upload/approval/revocation/search/citation,
readback/coverage/audit and honest retrieval-only pilot. Final115 tests, Ruff, strict
mypy36 files, build, exact-wheel isolated HTTP/Qdrant smoke and docs20 controls pass.
Single Medium post-auditor's four findings fixed and rereviewed; historical High reviews
retain their original effort records. New dispatches exclusively GPT6LunaMedium.
Docker unusable; checksum-pinned Qdrant1.19.2 musl build in WSL/Linux-owned storage is
the supported alternative. Owned test servers stopped; persistent test data retained.
Next: wait for P03 GO, then fresh Medium adversary/full-blueprint review before its tasks.
No generative provider call or new main push is authorized.

Previous verified foundation:

P01 is complete under explicit GO from 12dfc3f; package isolation proof and the single
post-audit resolution pass at E-P01-001. Existing Python 3.14.7 environment is reused;
uv.lock pins dependencies (Pydantic 2.14.1, PyYAML 6.0.3, pytest 9.1.1,
Ruff 0.17.1, mypy 1.20.2); build backend is pinned Hatchling 1.32.4.
Source: strict contracts/errors/IDs/fixture loader, settings, trusted access callbacks,
SQLite migrations/registry and content-addressed originals. Offline CLI uses actual
persisted authorization/approval and byte readers, not SQL-only helper assertions.
75 tests, strict typing/lint and optimized smoke pass; all three audit findings resolved.
Exact installed-wheel/locked isolated smoke passes (P01 evidence). P02 GO is now given.
PILOT fixtures: 4 sources, 3 cases/7 principals, 7 observations and exact T01–T24.
At P01 close no P02 subsystem existed. P02 now has retrieval/API and pilot evidence;
no provider call, human gold adjudication or full answer-system result exists.

P00 completion/old hold is historical at E-DOC-001–E-DOC-004. P01 GO supersedes only
that hold for this phase. Source/security gates remain PARTIAL until later consumers;
no P01 check establishes full message/runtime behavior. Root .env was never read or
copied; app .venv is reused/ignored. Unrelated .vscode remains untouched. New main
publishing requires explicit user approval; P03+ is outside current scope.

## Open risks to retain

Accepted directions and remaining evidence are separate: Q03/Q04 compatibility/language,
Q05 audit fixtures, Q07 configured synthetic freshness values, Q08 labels/calibration,
Q09 actual rubric/escalation assignment, Q10 optional-feature value; Q06/Q11/Q12 external
inventory/comparators/real deployment remain deferred. No unanswered recommendation is
silently promoted into empirical success.
No performance, completeness or production-readiness claim has been established.
