# Palladion working memory

Current checkpoint 2026-10-20: all 13 P10 cards complete against published feature checkpoint c3c0950 and E-P10-006–008. Source 458 PASS/32 explicit SKIP, installed 91 PASS/2 explicit SKIP, native PDF 1 PASS; additional parser controls pass in overlapping 11-test source/installed runs. Final 70-file package comparison, static/docs gates, current-phase Luna Medium review and owned cleanup pass. 125 of 126 total cards are checked; only P09-T02.07/PF03 performance acceptance remains OPEN. No full historical-document audit or production/semantic efficacy claim is made.

Updated 2026-10-20. Navigation aid only; user/vision/source/ADRs retain authority.

## Current P11 checkpoint (2026-10-28)

Source of truth for what changed and why: ADR-0102–0110 and E-P11-001 to E-P11-003. The evidence path is now: `Applicability` (storage/applicability.py) is the one rule for window and supersession, used by the resolver, the generation prefilter (`Catalog.eligible_generations`) and coverage; the agent's search takes the case's trusted instants from the request ledger, never from the model; `HybridSearch` returns ranked passages first with a quarter of the limit for context, defining chunks before citing ones, and counts why candidates were dropped; chunks keep a heading path and the index reads `index_text` (schema 8, representation fingerprint pins the text form, so earlier generations are unserved until indexed again). Recovery: if a deployment shows empty searches with `NO_ELIGIBLE_SOURCES`, index its revisions again. Chunks pack neighbouring whole sections up to `PACK_CHARS` = 600 (parser `mdtxt-v3`); the reranker takes passages shortest first; the audit a search runs counts points per generation (`counted_coverage`) and the count facet must not name its generations (888 ms against 25 ms). A code named in a title above a chunk defines it, the reranker orders only what the index found (the exact lane's chunks keep their place) and keeps the candidates past its depth (20 by default) after the reranked head, a code does not take a sentence's full stop, and `FAMILY@vN` in the user's own message (`RequestLedger.question`, never the model's query) names a version, numbered over the versions the reader can read (`Applicability.named`, `Catalog.family_version`). Open: P11-T06 (Track B and Track C re-run at the new commit when the provider quota renews, closeout); the long-lived search worker (12 to 14 s of start-up per agent search) needs the owner's decision; a multilingual reranker was evaluated and is too slow on this CPU. Reviewers for this phase are read-only Haiku 5.5 High.

## Current P10 verified checkpoint

All13P10cards are complete against published source checkpoint c3c0950; only P09-T02.07/PF03 remains open (125/126checked, not readiness).
ADR0096–0098 are accepted and verified: exact-proof scoped-admin graph HTTP; verbatim
UTF8/code and bounded pypdf6.21.0/SQLitev7 original/extracted/page provenance; lexical-2
weighted PathA and bounded own-session turn context consumed automatically. Four read
tools, canonical authority/ACL, graph default-off and opt-in local PathB are retained.

E-P10-006/007 and evidence/p10-consumer-observations.json own current measurements:
source458PASS32SKIP109.65s; installed91PASS2SKIP44.62s; actual installed Qdrant PDF1PASS
22.62s. Two later page/output controls pass within overlapping11-test source14.95s and
installed14.65s runs. Finalwheel70source/package/schema files match installed bytes;
wheel/sdist, ruff, mypy80files, dependency110files+4controls, docs126cards+21controls,
installed foundation/policy CLIs pass. Current classifier profile hash and30frozen/5
additional synthetic controls are in the receipt; these are not generalization proof.

Single LunaMedium start adversary and end reviewer read the complete blueprint; no
confirmed material source defect remained. Final parser evidence freshness resolved by
focused checks/rebuilt wheel. Owned Qdrant stopped and recorded PID absent; storage
preserved, Windows/WSL16333/16334/17687listeners absent. Neo4j not restarted on recovery.
Feature checkpoint c3c0950 is published to origin/main under owner approval; E-P10-008 records publication. Preserve
all foreign benchmark/editor changes; only our PALLADION_FIXES.md appendix is scoped.

Historical failures remain in E-P10-003–005/raw runtime logs: Windows98–99%RAM/uv1450/
CoreCLR/WSL failures; owner asked to retry, then host recovered. Do not infer a missing
Python installation from failed encodings startup under exhaustion. Earlier full suite
interrupted, not PASS. Actual service attempt1 Neo4j timeout, attempt2 smoke-setting
mistake; attempt3 all6graph/PDF/Groq/reopen checks passed9invocations8responses, one
causeUNKNOWN. Future observer records all outcomes. No frozen P08 reports are rewritten.

Next substantive unresolved outcome is PF03 performance, requiring separate bounded
planning/measurement before architectural changes. No new owner ADR answer is pending
for the completed P10 work; UI, enterprise writes and benchmark implementation excluded.

## Historical P09 recovery pointers

Read PROGRESS Active P09 checkpoint, all P09 cards, ADR0087–0095 and E-P09-001–004.
Owner rejected0091 closure: keep PF03 open. Owner approved0092 tenant-bound opaque IDs;
implemented returned-ID membership/ACL guards pass. ADR0094 batches canonical reads;
0095 owner-approved opt-in5second physical-audit caching is implemented; benefit is workload-dependent: large-case improvement, small-case overhead, expiry
misses. PF03/P09-T02.07 stays open. Current installed23guards+4actualQdrantchecks and
67package-byte proof PASS; sole end review resolved, owned Qdrant stopped/portsfree,
storage/backups retained. Scoped verified commit/push completes the mechanism checkpoint.
Current aliases: optional Catalog lookup limit101 with ACL before cap; ExactIndex100 and
public truncation warning. Budget tokenizer local-only, configured index cache. Current
study worker owns full process tree and retains partial UTF8/JSON/unknown accounting;
lightweight entry avoids importing whole study for helper controls. Source395broadPASS
plus23focusedguards, installed63earlier/23current and4currentrealQdrantchecks are separate
overlapping receipts. Shared914df24 alreadypublished the handoff response appendix;
our44-file checkpoint excludes all benchmark implementation/editor dirt. Do not repeat initial
baseline or spawn extra agents. Preserve foreign benchmark work and frozen P08 raw files.

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
