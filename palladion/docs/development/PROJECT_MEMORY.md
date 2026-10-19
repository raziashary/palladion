# Palladion working memory

Current checkpoint2026-10-20: P00–P08engineering work complete within the approved synthetic pilot boundary;98/98atomic cards and sole end-review resolution verified. P07 publishedf97471e; graph stays defaultoff. P08 outcomes are negative/inconclusive, semantic accuracy and unobserved candidate-stage metrics unknown. UI/enterprise writes/X01/benchmark-editor edits and a further main push remain excluded. Older dated snapshots are historical.

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

## Completed P08 recovery

P08 engineering pilot DONE, all12cards/98totalatomic cards checked, sole LunaMedium
end audit and same-reviewer R1–R4 resolution complete (E-P08-001–003). Current mandate
excludes UI/enterprise writes/X01/benchmark edits; further main push needs approval.
The verified scoped checkpoint containing this record preserves the work. No pending
owner architecture ADR; nextfree0087. Source/plans/evidence remain authoritative.

Frozen grid p08_0d19c2375c5c46d3ac792fd3c1e5da20 binds approved protocol/config
SHA987e3773fd6b0a1938d54c1e1903647d2e187e41142a9e7b05d05db2f29ce390.
44observations/16errors,91attempts/41rawresponses/45HTTP429/2HTTP400/3cancelled,
54750known tokens.12/12released citations resolve. Public P08_RESULTS.md and two bounded
receipts preserve adverse results, raw hashes, failures and accounting. No semantic/
causal/generalization/superiority claim. Raw source predates only later owning report,
asset-path, timeout and coverage corrections; never imply it equals the final source.

Fresh20B critic p06-57815987982f4322997fc434305ebe83 records16conditions,
16knownfactretained including fallbacks/0of4fullquotecorrections/0inventoryattestations.
Separate explicit120B continuity p05-b55c4c1197d646f299746de55263886f records3conditions,
currentstate/citation/no staleclaims, standardB5 answergapomission, allcompletionfalse.
Provider/quota/schema failures remain. Supplemental receipt contains per-attempt costs,
current24PASS versus separately retained historical20PASS4FAIL reconciliation.

R4/ADR0086 withdraws legacy candidate@5/10/20/fullMRR labels computed after finaltop4
truncation. New observed packet@4/packetMRR, unobserved candidate metrics unknown; raw
artifacts unchanged.20installed cutoff/report guardsPASS4.00s, current CLI replay44rows
with noticePASS. Final wheel65/65source bytes match SHA
d9795234c8820cc97de5df6200616fffed97cbfd4726fc4537774bd3167a0a3d.
Before report-only correction:360sourcePASS28explicitSKIP518.39s,37installedPASS39.21s;
current7installed integrationPASS217.35s, actualGroqinjection1PASS98.70s, canonical
44stores/12citations/21persistedrelease reopen and HTTP search/citation/ACL proof pass.
Checks overlap. Ruff/strictmypy75/dependency99+4controls/docs19MD98cards20controlsPASS.
No final combined full-suite exit0 is inferred from separate runs.

Earlier realserver47PASS6FAIL7SKIP and repeated graph failures, r3installedreadonly
failure, initial report-guard fixture/import/build failures remain in E-P08-002/003.
Cause of host delays unknown; no graph query/deadline rewrite. Owner kept other work
running; own Neo restart+serialized7currentchecksPASS, historical failures not erased.
Reviewer directly read blueprint§1–§18/I01–I15/all12docs and confirmed no material
finding remains after doc fixes and R4 correction; reviewer did not independently run tests.

Owned Qdrant/Neo/HTTP stopped through verified project launchers/process ownership.
Windows exclusive binds16333/16334/17687/18108PASS, no WSL listeners; storage and full
Qdrant/coldNeo backups preserved (E-P08-002). Never stop foreign benchmark services or
read/print root.env/demo_auth. Raw evidence under ignored runtime/evaluation; public
receipts contain bounded synthetic observations. Preserve concurrent .vscode/ and foreign
benchmark commits/worktree. Future work needs its own scope; research unknowns are not
permission to invent results or populate baseline/.

The P07 state below is historical; current P08 GO supersedes its next-action exclusions.

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
