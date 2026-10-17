# Palladion master development plan

Version 1, 2026-10-17. Scope anchor: [blueprint v0.2](../vision/palladion-blueprint-v2.md),
especially “Locked decisions,” “Build plan,” “System invariants,” and the full walkthrough.
The current user mandate is **P00 only**: create this development suite. P01–P08 describe
future system work. X01 is deferred comparison work. No UI phase is authorized.

## Document authority and ownership

| Record | Authority and update trigger |
|---|---|
| Current user instruction and applicable AGENTS | Scope/approval constraints; resolve before dependent work |
| Blueprint | Intended system architecture and locked constraints; do not quietly rewrite |
| Live source, schema, executed tests and measurements | Actual implemented behavior; a conflict with intent is a gap to surface |
| This plan + GOAL | Decomposition and acceptance, subordinate to user/blueprint; update when scope changes |
| ADR_LOG | Dated material decisions; append/supersede, never erase an inconvenient decision |
| TESTING_GATES + RESEARCH_PROTOCOL | Proof contracts; changes require rationale before measurements, not after failure |
| PROGRESS + EVIDENCE_LOG | Status and verification artifacts; link every closure to evidence |
| PROJECT_MEMORY + PROJECT_MAP | Recovery and navigation, not substitutes for source or vision |
| PROJECT_LEARNING + RISKS_AND_OPEN_QUESTIONS | Lessons with evidence, uncertain hypotheses and pending owner decisions |

All working documents are in this folder. The root README and AGENTS and docs README
only point here. Preserve the vision in `docs/vision/`. New facts that stale a document
must update it in the same unit, or be explicitly queued for the user's decision.

## Task reading and execution protocol

### Before every task

1. Read the current user request, root `AGENTS.md`, and any narrower applicable instructions.
   Check `git rev-parse --show-toplevel`, `git status --short --branch`, `git diff`, recent
   commits, and `git worktree list`. Preserve unrelated changes. Confirm starting revision.
2. Read [GOAL](GOAL.md), [PROGRESS](PROGRESS.md), and [PROJECT_MEMORY](PROJECT_MEMORY.md).
   Identify the active task and outcome, the latest verified checkpoint, and unresolved risks.
3. Read this plan's task row and phase exit, relevant [ADRs](ADR_LOG.md), and the relevant
   [risk rows](RISKS_AND_OPEN_QUESTIONS.md). Do not assume a proposed decision is accepted.
4. Read the full blueprint on first onboarding. On every subsequent task, reread the
   named blueprint sections in the row, “Locked decisions,” “System invariants,” and
   applicable runtime contracts. Read relevant representative code **with its warnings**.
5. Read the associated [testing gates](TESTING_GATES.md), [traceability rows](REQUIREMENTS_TRACEABILITY.md),
   and, for measurements, [research protocol](RESEARCH_PROTOCOL.md). Know how proof can fail.
6. Inspect the owning source, bodies, producers, consumers, schema/migrations, tests,
   configuration and permissions. Verify every named artifact exists before using it.
   The paths below are planned until implemented; absence is not an invitation to fake them.
7. State the intended unit, expected observation and required checks. Log decisions immediately.
   Seek direction where universal decision rules require it; no new architectural choice is
   implicitly approved by a task ID. Continue independent authorized work while waiting.

### During the task

Implement the smallest consumer-backed slice. Record progress at coherent checkpoints.
Derive negative tests from the contract, check valid cases still pass, and test writes through
their actual readers. Use synthetic isolated resources; inspect destructive test behavior
before running it. Credentials are command-local; do not copy them into worktrees.

Delegate read-heavy/fresh review only when useful. All subagents use `gpt-6-luna`, `high`;
dispatch exact inputs, allowed read/write paths, commands and prohibitions. Do not grant
live resources or git changes. Only the coordinator closes tasks/gates. No overlapping writers.

### Before closure

Run stack validation, the owning gates, and a representative entry-point smoke; record
exact commands, environment, observed results and limitations in [EVIDENCE_LOG](EVIDENCE_LOG.md).
Resolve material review findings or keep the task open. Update progress, affected goal
checkboxes, map/memory, learning and ADR/risk records. Run the docs checker and a no-stale
sweep. Stop task-owned processes and verify their ports are free; leave pre-existing services alone.
Deliberately stage reviewed files, scan for secrets, and commit a verified logical unit
with a Conventional Commit subject and descriptive body. Remote publishing follows the
user's explicit approval rules; current branch is `main`, so do not push without approval.
At a phase boundary, report and continue only within the current authorized scope.

## Baseline and path interpretation

Initial revision: `9b167a2a3fa61147d7104ed28d2f1a6bede1975c`, clean `main`, one worktree.
Only the blueprint was tracked. No code, dependencies, fixtures, tests or services existed.
The blueprint's `evidence-agent/` tree maps to **`palladion/`**; planned package remains
`src/evidence_agent/`. See ADR-0001. The 74-file map is a decomposition guide, not a quota
or claim that placeholder files are working capabilities.

## Sequence and status semantics

`P00 → P01 → P02 → P03 → P04 → P05 → P06 → P07 → P08` preserves blueprint Slice 0–7.
P02 records B0/B1 substrate results before graph. P06 measures the critic without graph;
P07 adds graph and enables full arm comparisons at P08. Arm names B0–B9 are treatments,
not chronological phase numbers. Telemetry and security start with the first runtime
slice; P08 broadens them rather than bolting them on at the end.

Task states: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`. Gate states:
`NOT_RUN`, `PARTIAL`, `PASS`, `FAIL`, `BLOCKED`. A plan checkbox is not proof. Implementation tasks
start `PLANNED`, all system gates start `NOT_RUN`; see [progress](PROGRESS.md).
Some gates span multiple phases: record the phase-local obligations and their evidence
as PARTIAL until the entire catalog contract is exercised. An early phase exits on its
own task/exit checks; it cannot claim a full multi-phase gate passed ahead of its consumers.

## P00 — Development suite

Goal D01–D05. Inputs: entire blueprint, current request and repository inspection.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P00-T01 | Read full vision and establish authority, layout, scope | All 18 sections mapped; blueprint preserved; ADR-0001–ADR-0003 |
| P00-T02 | Create linked plan, goal, gates, ADR, learning, memory, map, risks and research records | Every document has a distinct owner/function and task-start navigation |
| P00-T03 | Validate references/IDs, independently audit blueprint fidelity, fix findings | G-DOC; positive and deliberate-failure validator checks; E-DOC-001; reviewed commit |

Exit: documentation is usable by the next session; no system gate or hypothesis declared passed.

## P01 — Corpus, contracts, and adversarial fixtures (Slice 0)

Goal O01/O02 foundation. Read blueprint “Corpus, contracts, and adversarial fixtures,”
“Core typed contracts,” “Canonical SQLite schema,” “Test corpus and annotation protocol,”
and “Remaining open issues.” Depends on P00. Owner modules: core, security foundation,
storage schema/settings, synthetic corpus. No model calls needed.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P01-T01 | Establish Python packaging/tooling and mock-first validated config; decide approval fixture trust model and dependency pins | ADRs close Q01/Q02; no secrets; explicit paid-call enable flag; documented runnable commands; G-CONTRACT |
| P01-T02 | Typed schema-versioned Principal, Evidence, Claim, Observation, PolicyDecision, Packet, review/gate and errors; case memberships and immutable source IDs | Reject unknown/invalid fields; schema round trips; identity injected by backend; G-CONTRACT, G-SECURITY |
| P01-T03 | SQLite schema, transaction/migration strategy and synthetic approval/case registry | WAL/FK checks; original bytes immutable; event/ACL producer read by resolver; isolated fixtures; G-SOURCE |
| P01-T04 | Fictional approved old/current SOP, exceptions, drafts, two tenants and cases, policies/timestamps; gold annotation schema | Each golden names required refs/slots/time basis, allowed hypotheses, forbidden actions and disposition; T01–T24 fixtures catalogued; G-CONTRACT |

Exit: deterministic corpus/contracts validated without LLMs; hand-authored labels reviewed.
Meaningful research labels later require two annotators and adjudication; automation is not independent truth.

## P02 — Provenance-first retrieval (Slice 1)

Goal O01. Read blueprint “Document ingestion,” all “Hybrid document retrieval,” “First
build slice versus full map,” Qdrant example warnings, and “Index consistency and revocation.”
Depends on P01. Owner modules: storage, ingest, retrieval, API citation/source endpoints.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P02-T01 | Immutable MD/TXT parser/chunker and authenticated metadata; staged ingest with manifests and retry/recovery | Exact accepted IDs/counts/hashes reconcile; no partial generation published; graph-status marker optional; G-SOURCE |
| P02-T02 | Pin/verify Qdrant/client, embedding and BM25 mode/tokenizer; same point ID with named dense/bm25; payload indexes before ingest | Integration proves supported native RRF `k=60`, single fusion, matching ingest/query representation; Q03/Q04; G-RETRIEVAL |
| P02-T03 | Scoped dense+sparse union, exact-ID injection, canonical ACL/approval/time resolver, parent/exception expansion; optional reranker treatment | Known wrong ID is rejected; post-expansion recheck; cite original spans, never generated prefix; G-RETRIEVAL, G-SECURITY |
| P02-T04 | Authenticated upload/approval/index-health and citation endpoints; baseline B0/B1 then B2 measurements | Upload→search→GET citation exact-byte consumer smoke; revoke→deny; per-stage recall and failure record; G-SOURCE, G-RETRIEVAL |

Exit: actual indexed synthetic source can be cited under the authorized principal; old/draft
matches cannot authorize current guidance. Retrieval independently benchmarked before agent/graph.
No-critic retrieval measurements do not authorize consequential released answers.

## P03 — Temporal policy and read-only mock observations (Slice 2)

Goal O02. Read blueprint “Policy-specific temporal applicability,” all “Deterministic
policy system,” “Live operational / BI adapters,” temporal/evaluator sketches and warnings.
Depends on P02. Owner modules: policy, live, related storage/security/audit.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P03-T01 | Approved policy registry and deterministic temporal resolver with scope, four bases, trusted timestamps, valid/record time, explicit supersession | Boundaries/overlap/cutoff and mixed-basis conflict tests; concurrent registry updates cannot silently choose an overlap; G-TEMPORAL |
| P03-T02 | Validated bounded safe predicate AST, required inputs, provenance/freshness and source-linked decision traces | No eval/SQL; missing ≠ false; conflicting rows ≠ winner; replay trace in reader; G-POLICY |
| P03-T03 | Named read-only mock adapters, server identity and target auth, strict schemas, timestamp semantics, limits/retries/redaction | All typed statuses tested; stale data_as_of not rescued by observed_at; no dynamic endpoint/write; G-LIVE, G-SECURITY |

Exit: event-time and current handling can select different valid policies; missing settlement
state returns `INCOMPLETE_INPUT`; mock snapshots and policy traces are consumed by real domain readers.

## P04 — Bounded main agent and deterministic gate (Slice 3)

Goal O03. Read blueprint “Complete runtime flow,” “Runtime interfaces,” “Claim-level
assessment,” “Explicit answer statuses,” budget/gate sketches and walkthrough. Depends on P03.
Owner modules: agent excluding full critic, API, ledger, packet skeleton and audit.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P04-T01 | Provider-neutral deterministic fake LLM, four authorized tool facades, nonexclusive preflight and canonical evidence ledger | Server identity cannot be overridden; tools don't bypass domain ACL; multi-tool question stays possible; G-SECURITY, G-BUDGET |
| P04-T02 | Investigation→draft→review boundary→finalization state machine with pre-reserved accounting and global deadline | ≤5 main incl failed/malformed calls, reserve final; tools/retries/cancellation capped; no sixth repair; G-BUDGET |
| P04-T03 | Typed claims, requirement origins, deterministic per-claim eligibility and five dispositions; safe renderer and protected rejected diagnostics | Model answer-kind/hypothesis labels cannot evade risk/requirements; unknown refs and unsupported directives blocked; G-GATE |
| P04-T04 | Message API, citation API, timeline/trace, health/ready, persisted tool failures; synthetic vertical smoke | Authenticated message→verified refs→reader; 5 dispositions; no evidence/tool/conflict paths; G-E2E, G-SECURITY |

Exit: fake-model end-to-end path and correct abstention proven. Until P06 real critic exists,
normative released outputs use unavailable/non-actionable partial safety behavior; a mock
review is test plumbing, not evidence that mandatory review has occurred. Gate adequacy is
necessary-condition checking, never a complete semantic proof system.

## P05 — Memory and continuity (Slice 4)

Goal O04. Read all blueprint “Continuity packet and SQLite memory,” “Error classes,
retries, and resumability,” and “Memory write protocol.” Depends on P04. Owner: memory/events.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P05-T01 | Append-only events, episodic/semantic/procedural categories, USER/CASE/TEAM/ORGANIZATION scope, explicit promotion | User/model claims cannot become global policy; user-controlled validity provenance; G-MEMORY |
| P05-T02 | Application-generated bounded packet, structured/FTS recall, scope/hash/generation keyed hot cache | Evidence handles reread under current ACL/time; revocation invalidates cache; unspecified lifetime retained; G-MEMORY, G-SECURITY |
| P05-T03 | Follow-up/resume path with corrections, role changes and updated live observations | New message consumes previous events but refreshes material evidence; long-session loss metrics; G-E2E, G-MEMORY |

Exit: a second request preserves reported/observed/hypothesis distinctions without granting
old evidence current authority. Optional sqlite-vec remains an ablation, not a dependency.

## P06 — Adversarial critic experiment (Slice 5)

Goal O05. Read blueprint “Adversarial Evidence Critic,” “Explicit experimental arms,”
“Adversarial critic reliability,” and critic outage/budget hard cases. Depends on P05.
Owner: critic/loop integration, paired evaluator and audit.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P06-T01 | Independent-context structured critic, reference validation, normally one call, ≤3 total and ≤2 counter-searches | Invented challenges cannot fabricate conflict; all new evidence revalidated; G-CRITIC, G-BUDGET |
| P06-T02 | Mandatory normative/operational review, failure policy, revision/finalization wiring | Critic outage/malformed responses cannot yield unsupported approval; no budget escape; G-GATE, G-CRITIC |
| P06-T03 | Frozen draft+initial evidence paired critic on/off, fixed-context vs counter-search, blind-requirements variant | Attribute genuine corrections/false vetoes and changed evidence; report shared blind spots and extra cost; G-RESEARCH |

Exit: supported exception correction demonstrated with failures preserved; false-veto and
cost measured. Do not claim reliability from agreement or silently activate adaptive bypass.

## P07 — Optional source-linked graph (Slice 6)

Goal O06. Read all blueprint “Knowledge graph,” “Graph integration only after baseline,”
and graph identity/leak/fan-out hard cases. Depends on P06 and P02 baseline evidence.
Owner: graph, Neo4j storage, graph extraction/expansion and ingest reconciliation.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P07-T01 | Verified namespace keys and uniqueness constraints, provisional IDs, reviewed merge audit, typed provenance edges | Concurrent same identity dedupes; same names distinct IDs never merge; G-GRAPH |
| P07-T02 | Optional bounded traversal, canonical neighbor resolution, graph on/off publication requirements and outage behavior | Scope/hops/fan-out/time caps; source recheck before model; required relation unavailable vs optional fallback; G-GRAPH, G-SOURCE |
| P07-T03 | Paired B2/B3 experiment on frozen retrieval corpus, review effort and costs | Recover known missed exception in selected case, evaluate aggregate harm/benefit; record retain/disable decision; G-RESEARCH |

Exit: evidence and cost justify feature state. If no improvement, keep graph disabled and
record negative result; do not fabricate a passing aggregate claim from one showcase.

## P08 — Scientific evaluation, observability and fault injection (Slice 7)

Goal O07. Read all blueprint “Research evaluation,” “Security, privacy, observability,”
and “Final design rules.” Depends on P01–P07 exits or documented graph-disabled decision.
Owner: evaluation/reconciliation scripts, telemetry, security/golden/end-to-end tests.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P08-T01 | Freeze corpus/splits/gold adjudication, configs/prompts/pins, metric denominators and development-calibrated targets before held-out run | Run manifest and preregistration; no held-out tuning; G-RESEARCH |
| P08-T02 | B0–B9 controls and paired ablations; repeated stochastic runs, multilingual/ACL/time/difficulty slices, safety and usefulness | Full run/failure records, confidence intervals and non-applicability labels; G-RESEARCH |
| P08-T03 | Full T01–T24, injection/redaction, partial outages, ACL/approval races, retry/deadline/cancellation and replay | G-SECURITY, G-E2E, G-BUDGET; unauthorized content absent from prompts/cache/response/trace |
| P08-T04 | Export reproducible report with latency/cost tails, failure ownership, negative results and prototype limits | Reader can reconstruct run from manifest; no production claims; G-RESEARCH |

Exit: all integrity gates pass on the declared corpus and conclusions follow measured data.
A failed improvement hypothesis remains a completed experiment if honestly reported; an
integrity failure prevents demonstrating consequential answers as supported.

## X01 — Later external comparator program (deferred)

Goal O08. User reserves `baseline/` for standard RAG, LangChain RAG and provider-system
comparisons. No baseline implementation, dependency installation or provider spending now.
After system and evaluation interface stabilize: define capability-matched tasks, integrate
isolated comparator adapters, freeze common inputs and resource tracks, run held-out tests,
and publish multidimensional results under [RESEARCH_PROTOCOL](RESEARCH_PROTOCOL.md).
Implementation-library labels alone are not experimental treatments.

## Definition of done

A task is done only when acceptance, relevant gates, runnable smoke, review findings,
current documents and scoped checkpoint all have evidence. Gate skips require explicit
reason and remain unpassed. Never silently lower thresholds, delete failures, cite absent
test files as executed, or claim an experimental module exists because the plan names it.
