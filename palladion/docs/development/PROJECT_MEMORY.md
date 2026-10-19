# Palladion working memory

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

P06 DONE at E-P06-001/E-P06-002: all six atomic cards, approved critic/status/pacing
contracts, actual source/installed/API consumers and sole Luna Medium end-review
resolution are verified. Source294PASS plus13 actual-Qdrant cases pass (12 in the sweep,
one isolated after a setup connection-abort) =307 disjoint checks. Installed294 and one
installed real-Qdrant/API case pass as overlapping artifact checks; all50 packaged files
match the final wheel. Ruff, strict mypy59, dependency81+4controls, foundation CLI and
final document gates pass. Original failed/skipped runs remain evidence, not PASS.

Post-fix real20B exact recoveryPASS39.827s (2main/2critic/1search, explicit cap2) and
serialized default-budget MODEL-draft pathPASS37.089s (4main/1critic/2tools) release the
full exception with original citation/timeline readback and no verification errors.
Gate qualifies a changed final proposal or unresolved CHALLENGE while preserving
canonical facts; unchanged current PASS remains eligible for SUPPORTED. Model review
is advisory, not semantic authority or payment permission.

Frozen prompt-version20B matrix cb9e66:16conditions,16/16known-fact retention,
0/4full-exception corrections, one critic validation failure,16main/17critic/4searches,
66117known received tokens (one attempt lacks usage). It precedes ADR0062's gate-only
qualification fix: no model prompt changed; raw outputs are not relabeled post-fix.
No efficacy/H05, semantic accuracy, causal false-veto or completeness claim. Mandatory
review remains enabled; draft-blind first pass sees canonical required slots (§10.1).
P07 graph/P08 adjudicated research/X01 comparators remain deferred; no P07 GO or P06
main push is inferred. No unanswered P06 owner ADR. Owned processes stopped, storage
preserved and ports16333/16334/18080 verified free; foreign benchmark/editor work untouched.


P03 published64d2066; P04 published4245023. Preserve concurrent benchmark/.vscode work.

P05 DONE at E-P05-001; all seven cards and third-turn correction verified with the same reviewer. Approvedv4
adds immutable memory provenance/team/FTS with checked pre-migration backups; no user
demo DB migrated. Four scopes require current principal/origin-case/source permissions.
Owner/admin validity edits, explicit promotion and revisions remain context-only.
Packet carries historical RECHECK observations, unverified reports, hypotheses, gaps
and attempts. Empty failed replies cannot clear prior incomplete policy questions;
current authorized decisive policy traces determine their continuity. Every HotCache hit revalidates source bytes/time/ACL/generation; no speed
claim. Recall scopes/active state filter before500candidate bound and reports
non-exhaustive coverage;501private-row starvation controls pass. Same reviewer resolves
R1/R2 and third-turn correction;17targetedPASS. Latest246source+12actual-Qdrant=258disjointPASS, installed65
(overlap)PASS, Ruff/mypy58/dependency79+4/doc controlsPASS. Final49file wheel SHA256
6ab0757572b84aeb51ad24611d746ba45a616ce782b1d90cfa6403b9bcf8775f.
Actual120B pilot p05-a3c0f62508844c53bb29288c590fb0a4 exits0/allconditions, setup true,
packet gap recall0/1/1, strictcompletion0/3 due provider400errors. FreshPENDING, no
staleFAILED claims; compressed answer omitted settlement. All failures retained, no
H04/reliability/semantic claim. Scorer/guard evidence is separate from actual provider
proof. OwnedQdrant99335/PID471 stopped,0collections, ports16333/16334/18080 free.
Ignored wheel environment retained without processes. Benchmark/.vscode untouched.
P05 now pushed f0507e4 under new owner approval. P06 GO is active; see E-P06-001 and accepted ADR0045/0046 for contract/pilot changes. Another main push and P07 need separate authorization.

Previous P02 state:

P02 DONE from published aa4b439; E-P02-001, ADR-0025/0026. All15 children verified:
canonical ingestion/catalog, approved additive schema v3, actual dense/BM25 Qdrant,
exact-ID/canonical/ACL retrieval, authenticated upload/approval/revocation/search/citation,
readback/coverage/audit and honest retrieval-only pilot. Latest117 tests, Ruff, strict
mypy37 files, build, exact-wheel isolated HTTP/Qdrant smoke and docs20 controls pass.
Single Medium post-auditor's four findings fixed and rereviewed; historical High reviews
retain their original effort records. New dispatches exclusively GPT6LunaMedium.
Docker unusable; checksum-pinned Qdrant1.19.2 musl build in WSL/Linux-owned storage is
the supported alternative. Owned test servers stopped; persistent test data retained.
P02 publication and its dependency/generation follow-up completed at f48ad05.
That prior approval is historical; current P03 GO does not authorize a new main push.

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
at that P01 checkpoint no provider call, human gold adjudication or full answer-system result existed.

P00 completion/old hold is historical at E-DOC-001–E-DOC-004. P01 GO supersedes only
that hold for this phase. Source/security gates remain PARTIAL until later consumers;
no P01 check establishes full message/runtime behavior. At P01 root .env was never read or
copied; P04 explicit enabled commands now read only the selected Groq credential internally, never print/export it; app .venv is reused/ignored. Unrelated .vscode remains untouched. New main
publishing requires explicit user approval; P07+ is outside current scope.

## Open risks to retain

Accepted directions and remaining evidence are separate: Q03/Q04 compatibility/language,
Q05 audit fixtures, Q07 configured synthetic freshness values, Q08 labels/calibration,
Q09 actual rubric/escalation assignment, Q10 optional-feature value; Q06/Q11/Q12 external
inventory/comparators/real deployment remain deferred. No unanswered recommendation is
silently promoted into empirical success.
No performance, completeness or production-readiness claim has been established.

Owner approved ADR0053 via async reply2026-10-19 (supersedes earlier pending
checkpoint text). Opt-in model-call pacing defaults0 and is now implemented, with
post-wait caller authorization/evidence validation. Focused98checksPASS15.51s;
actual paced message proof and phase checks now pass; sole end review resolved R1/withdrew R2; final gates and cleanup verified.
ADR0054 strengthens pre/post critic discovery attribution and safe attempt diagnostics.

End-review R1 confirmed: ADR0062 qualifies changed final proposals and unresolved
CHALLENGE without erasing canonical facts. Final matrix cb9e66 remains its unchanged
model/prompt/launch-gate version; qualification-only gate correction follows it. Quote,
fact-retention and model-cost observations are not relabeled as post-correction outputs.
Post-fix stack/installed/live checks and same-reviewer resolution precede closure.
