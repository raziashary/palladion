# Palladion working memory

Current checkpoint2026-10-19: P06 published6444345; P07 graph and owner-added automatic memory implementation, consumer proof and sole LunaMedium end-review resolution verified (E-P07-001/002). ADR0063–0066 owner approvals preserved. Graph stays off after zero incremental recoveries. P08/UI/benchmark edits and another main push remain excluded. Older phase snapshots below are historical.

Updated 2026-10-19. Navigation aid only; user/vision/source/ADRs retain authority.

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
- Subagents only for the start adversary and end reviewer, both **GPT 6 Luna Medium**.
  Coordinator owns research, implementation and testing; reuse reviewer for resolution. Every phase requires one pre-phase
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

P07 DONE, all11cards verified at E-P07-001/002; verified checkpoint is recorded in scoped git history. P06 published6444345. Foreign benchmark commits advanced shared main during this phase; preserve their history/dirt and detached benchmark artifact worktree. No P07 main push or P08/UI/enterprise authorization.

One LunaMedium start adversary read the complete blueprint and re-reviewed owner-added memory scope. One LunaMedium end reviewer independently read all18sections/I01–I15, source, all12developmentdocs and evidence. Three current-facing docs contradictions fixed and same reviewer confirmed resolved; graph stale-generation exposure suspicion refuted by active-generation READY checks. No confirmed source defect remained. Accepted ADR0063–66 cover graph/v5/admin ACL/isolated WSL and memory/v6/private USER semantics/explicit sessions/primary deterministic PathA. ADR0067–70 cover physical projection, frozen promotion profile, bounded local job and navigation versus incremental recovery.

Graph: canonical SQLite attestations/reviews/merge history; exact projection/publication physical Neo4j readback; source-backed typed bounded traversal through opt-in HybridSearch/API and real credential-free worker. Paths navigation_only; canonical source/policy/gate authority retained. Defaults graph off/2seconds unchanged; positive pilot explicitly uses10seconds. Frozen4pair B2/B3 run finds0incremental recoveries (both expected appendices already found by B2), so graph stays off. Actual worker6.93s/OK/1path/original readback and actual CLI/API/Groq consumer proof pass. Initial slow/degraded and seed-timeout runs remain failures, not reliability claims.

Memory: additivev6/session lifecycle; automatic bounded PathA after original event commit, atomic chunks/decisions/MemoryStore/links; exact UTF8 spans/hash/current origin ACL; corrections/revocation prevent resurrection. Episodic packet/recall is session-only; USER preferences cross sessions; procedural experience stays unapproved authorityNONE. Canonical case evidence/audit remains separate. Explicit scripts/promote_memory.py --enable-path-b invokes cached pinned local encoder, max8events/64chunks/30seconds kill/join, no Groq classifier. Frozen uncalibrated rulesweight.8/cos.75/margin.1/combined.65 and full model/profile scores/loss persist. Local6eventpilot4mechanical labels pass/2semantic labels unknown,1embeddingcall12texts/0provider; no Bpromotion. Prototype positive is an integration control, not generalization.

Current evidence: default327PASS/25explicit integration-providerSKIP68.40s. Real-server sweep345PASS/1seed-timeoutFAIL/6GroqSKIP379.97s, then same test within10isolatedPASS78.15s:346distinct non-provider checks have positive evidence, not a combined exit0. Final graph guards9PASS24.85s. Installed55PASS/2modelSKIP +actualgraph/localmodel2PASS +latestguard1PASS overlap. Wheel62/62source bytesmatch SHA2560e09cb80cd10ff9908e6b3ceb86f824d4c02df05ce2b984b773c64fa388d582a. Ruff/strictmypy72/dependency96+4controls/doc17MD98cards20controls and actual foundation/policy CLI proof retained.

Normal persistent CLI proof: unique-root seed/reconcileall_match → serveHTTP18080 → actual Groq20B paced10s → next explicit session → citationHTTP. First59.92s5main+1critic3tools; next41.95s3main+1critic1search,1path/1citation/noverificationfailures, private preference consumed/reopened and oldepisodeabsent. Both bounded public JSON receipts in docs/development/evidence; rawruntime/provider/storage/model/build artifacts ignored. No truth/personalization accuracy inferred.

Cleanup: owned HTTP18080 and WSL Neo4j17687/Qdrant16333+16334 stopped; preserve ~/.local/share/palladion/{neo4j-p07,qdrant} and synthetic CLI corpus. Do not touch foreign services or credentials. Final exact port/static/staged verification is in E-P07-002. Next action: await owner P08/mainpush GO; no pending P07 owner ADR.

## Earlier completed boundaries

P01–P06 evidence lives in EVIDENCE_LOG; P03 published64d2066, P04at4245023, P05atf0507e4, P06at6444345. P06 final307disjoint checks, installed/live proof and sole end-review resolution. Frozen16condition critic pilot retained16/16knownfacts but0/4full-exception corrections, one critic validation failure; no efficacy/H05/semantic-accuracy claim. No earlier phase receipt closes newly added P07 obligations.
