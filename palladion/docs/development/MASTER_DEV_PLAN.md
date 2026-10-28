# Palladion master development plan

Current checkpoint 2026-10-20: all 13 P10 cards complete against published feature checkpoint c3c0950 and E-P10-006–008. Source 458 PASS/32 explicit SKIP, installed 91 PASS/2 explicit SKIP, native PDF 1 PASS; additional parser controls pass in overlapping 11-test source/installed runs. Final 70-file package comparison, static/docs gates, current-phase Luna Medium review and owned cleanup pass. 125 of 126 total cards are checked; only P09-T02.07/PF03 performance acceptance remains OPEN. No full historical-document audit or production/semantic efficacy claim is made.

Version 13, 2026-10-20. Scope anchor: [blueprint v0.2](../vision/palladion-blueprint-v2.md),
especially “Locked decisions,” “Build plan,” “System invariants,” and the full walkthrough.
Historical P06 checkpoint: P05 published f0507e4; **P06 DONE** locally, all six atomic cards verified at E-P06-001/E-P06-002 with sole Luna Medium end audit/resolution,307disjoint checks, installed/live proof and cleanup. Paired results remain neutral for full exception correction; no research success is claimed. P06 is now published; P07 GO and ADR0063–65 accepted. P08 and another main push require approval.
P04 includes actual Groq, four tools, packet/ledger, bounded investigation/finalization,
deterministic gate and authenticated message/citation/timeline/trace consumers.
P05 push completed; no further main push inferred. P08 now has owner GO; X01/UI remain outside scope.
ADR-0011 governs; ADR-0013 selects uv and real Groq generation. E-P04-001 records work.

## Document authority and ownership

| Record | Authority and update trigger |
|---|---|
| Current user instruction and applicable AGENTS | Scope/approval constraints; resolve before dependent work |
| Blueprint | Intended system architecture and locked constraints; do not quietly rewrite |
| Live source, schema, executed tests and measurements | Actual implemented behavior; a conflict with intent is a gap to surface |
| This plan + GOAL | Decomposition and acceptance, subordinate to user/blueprint; update when scope changes |
| ADR_LOG | Dated material decisions; append/supersede, never erase an inconvenient decision |
| TESTING_GATES + RESEARCH_PROTOCOL | Proof contracts; changes require rationale before measurements, not after failure |
| Atomic checkboxes + PROGRESS + EVIDENCE_LOG | Plan owns child task state; PROGRESS derives phase/active-task summaries; evidence proves closure |
| PROJECT_MEMORY + PROJECT_MAP | Recovery and navigation, not substitutes for source or vision |
| PROJECT_LEARNING + RISKS_AND_OPEN_QUESTIONS | Lessons with evidence, uncertain hypotheses and pending owner decisions |

All working documents are in this folder. Root README and docs README provide entry
points; root AGENTS governs the workflow and links here. Preserve the vision in
`docs/vision/`. New facts that stale a document
must update it in the same unit, or be explicitly queued for the user's decision.

## Task reading and execution protocol

### Before every task

1. Read the current user request, root `AGENTS.md`, and any narrower applicable instructions.
   Check `git rev-parse --show-toplevel`, `git status --short --branch`, `git diff`, recent
   commits, and `git worktree list`. Preserve unrelated changes. Confirm starting revision.
2. Read [GOAL](GOAL.md), [PROGRESS](PROGRESS.md), and [PROJECT_MEMORY](PROJECT_MEMORY.md).
   Identify the active task and outcome, the latest verified checkpoint, and unresolved risks.
3. Read this plan's parent task row, exact atomic child card and phase exit, relevant [ADRs](ADR_LOG.md), and the relevant
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

Standing delegation limit (owner 2026-10-18): subagents only for the start adversary
and end reviewer, both GPT 6 Luna Medium. All investigation, implementation and tests
belong to the coordinator. Reuse the end reviewer for resolution checks; do not dispatch
intermediate research, implementation or testing agents. Historical dispatches remain receipts.

### Before each phase

Before each phase (including a newly scoped documentation phase), dispatch a GPT 6 Luna
Medium adversary to challenge the task/dependency/file/proof assumptions. The coordinator
verifies findings, corrects the plan/gates and records the preflight receipt before work.
Recheck materially changed phase premises; an old receipt does not authorize a new scope.

### Blueprint review contract for both reviewers

Every pre-phase adversary and the single post-phase work auditor must read the complete
[blueprint v0.2](../vision/palladion-blueprint-v2.md) (§1–§18) directly in a fresh context.
The dispatch names that exact file, current user amendments/accepted ADRs, phase tasks and
exits, gates, traceability and live source/test/evidence paths. A coordinator summary or
task-card-only review cannot replace this read. Reviewers remain read-only, GPT 6 Luna
Medium, without credential/live-resource access or git mutations.

The adversary checks whether tasks, dependencies, files and proof can fulfill the vision.
The auditor checks the actual diff, intended consumers, executed checks and remaining
obligations against that same vision. Both explicitly assess:

- §1/§17 locked decisions, authority boundaries and invariants, including recorded owner
  overrides; representative snippets do not override their surrounding warnings.
- §3/§11/§13.5 flow: deterministic nonexclusive preflight with zero LLM calls; exactly
  four authorized read tools; main calls ≤5 total including finalization; critic calls
  ≤3, normally one; separately bounded tools/prefetch/counter-search/retries and global
  deadline. Failed/malformed attempts still count; no sixth main repair call.
- Draft → advisory critic and any authorized bounded counter-search → reserved main
  finalization → deterministic final gate → safe rendering and persisted continuity.
  New evidence requires revalidation. Before P06, missing mandatory review cannot yield
  supported normative guidance. Optional planner/graph/vector/adaptive treatments remain
  controlled experiments, not implicit base-architecture changes.
- Applicable source/ACL/time/policy/live/memory contracts, §14 hard cases and research
  controls, §15 build sequence, §16 security/observability and §18 walkthrough.

Each EVIDENCE_LOG receipt names full-read coverage, relevant blueprint headings/invariants,
task → consumer → gate/evidence links, and confirmed/refuted/partial/uncertain claims.
Unbuilt later capabilities retain an explicit owning task, never an early PASS. Findings
record consequence, disposition and verification. The coordinator checks load-bearing
findings; material unresolved drift or missing coverage keeps the affected phase open.
A review receipt cannot substitute for behavioral evidence.

### During the task

Implement the smallest consumer-backed slice. Record progress at coherent checkpoints.
Derive negative tests from the contract, check valid cases still pass, and test writes through
their actual readers. Use synthetic isolated resources; inspect destructive test behavior
before running it. Credentials are command-local; do not copy them into worktrees.

Only the start adversary and end reviewer may be delegated; the coordinator does all
intermediate work. Required pre/post phase reviews are mandatory, not discretionary. All subagents use `gpt-6-luna`, `medium`;
dispatch exact inputs, allowed read/write paths, commands and prohibitions. Do not grant
live resources or git changes. Only the coordinator closes tasks/gates. No overlapping writers.

### Before closure

Run stack validation, the owning gates, and a representative entry-point smoke; record
exact commands, environment, observed results and limitations in [EVIDENCE_LOG](EVIDENCE_LOG.md).
After stack validation, smoke and owning gates, dispatch one GPT 6 Luna Medium work auditor
to inspect the completed phase and actual evidence using the blueprint review contract
above. Resolve material findings or keep
the task open. Update progress, affected goal
checkboxes, map/memory, learning and ADR/risk records. Run the docs checker and a no-stale
sweep. Stop task-owned processes and verify their ports are free; leave pre-existing services alone.
Deliberately stage reviewed files, scan for secrets, and commit a verified logical unit
with a Conventional Commit subject and descriptive body. Remote publishing follows the
user's explicit approval rules; current branch is `main`, so do not push without approval.
At a phase boundary, report and continue only within the current authorized scope.
For P00-T05, coordinator and that one post-phase auditor each check all development
Markdown documents against the complete 18-section blueprint; check_docs.py supports
structure only. Preserve per-document coverage/findings in E-DOC-003 and final E-DOC-004.
Publish only verified documentation under the user's explicit main-push approval,
then WAIT_FOR_GO for P01.

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

### Atomic task contract

The original Pxx-Txx rows below are **work packages**, retained so existing references
remain valid. Execute their child checkbox tasks in the [atomic execution register](#atomic-execution-register).
`P01-T01.01` is a stable child of P01-T01; suffixes are never reused or renumbered.
Unchecked means unproven, not absent effort. Record in-progress/blocked detail in PROGRESS.
Parent references mean the complete package, never an arbitrary child. Every package and
phase exit retains its original acceptance; completing children alone cannot waive it.

Each atomic card specifies exact repository-relative **Files**, explicit **Depends**,
bounded **Change** with its reader, and **Proof** (kind, gate, positive/negative observation).
Paths are planned unless already in this documentation suite. P01 foundation files now exist; later-phase paths remain planned until proved.
Evidence kind means: DOC = structural/content check; UNIT = deterministic isolated behavior;
INTEGRATION = actual local store/domain boundary; SMOKE = real API/script entry point;
MEASUREMENT = recorded comparative result. These are proof requirements, not earned badges.

Before executing a card, verify its named files/contracts against current source and the
blueprint, resolve its open owner/dependency decisions, and inspect tests. Shared files
may be touched by multiple **sequential** cards; dependencies do not permit concurrent
writers. File lists are bounded change ownership, not blanket edit permission for every
neighboring module. Add the smallest needed test in the named test file alongside the
behavior. Task closure records changed paths, actual consumer/readback, commands, evidence
ID and limitations directly beneath its checkbox; flip it only after those checks pass.
Card dependencies supplement the phase prerequisites; they do not authorize entering a
later phase before the preceding phase exits. Read root AGENTS “Evidence and execution
rules” and “Phase closeout order” on every task, including pre-build refutation and
meaningful negative controls (ADR-0010).

Arcana's master plan and companion family were read as a formatting/granularity reference
at `C:/arcana/docs/restructurization/development/`. Palladion's blueprint still determines
the files, architecture and slices. No Arcana-specific runtime, UI, score or approval rule
is adopted (ADR-0009).

## P00 — Development suite

Goal D01–D07. Inputs: entire blueprint, current request, Arcana documentation reference
and repository inspection. D01–D05 cover initial setup; D06 covers the atomic-plan/rules refinement.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P00-T01 | Read full vision and establish authority, layout, scope | All 18 sections mapped; blueprint preserved; ADR-0001–ADR-0003 |
| P00-T02 | Create linked plan, goal, gates, ADR, learning, memory, map, risks and research records | Every document has a distinct owner/function and task-start navigation |
| P00-T03 | Validate references/IDs, independently audit blueprint fidelity, fix findings | G-DOC; positive and deliberate-failure validator checks; E-DOC-001; reviewed commit |
| P00-T04 | Refine the suite into atomic file-specific work using the requested Arcana documentation reference | Atomic cards, file/dependency coverage, synced companion records, independent audit; E-DOC-002; G-DOC |
| P00-T05 | Record accepted answers, use editable ADR format, select uv/Groq, require phase reviews, and verify full vision fidelity | E-DOC-003; mandatory pre-adversary and single post-auditor; coordinator and auditor check every development doc; WAIT_FOR_GO |

Exit: documentation is usable by the next session; no system gate or hypothesis declared passed.

## P01 — Corpus, contracts, and adversarial fixtures (Slice 0)

Goal O01/O02 foundation. Read blueprint “Corpus, contracts, and adversarial fixtures,”
“Core typed contracts,” “Canonical SQLite schema,” “Test corpus and annotation protocol,”
and “Remaining open issues.” Depends on P00. Owner modules: core, security foundation,
storage schema/settings, synthetic corpus. No model calls needed.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P01-T01 | Apply accepted approval direction, uv packaging/tooling and explicit Groq runtime configuration | ADRs ADR-0012/ADR-0013 govern; no repeated owner vote; no secrets; explicit live-call enablement; documented uv commands; G-CONTRACT |
| P01-T02 | Typed schema-versioned Principal, Evidence, Claim, Observation, PolicyDecision, Packet, review/gate and errors; case memberships and immutable source IDs | Reject unknown/invalid fields; schema round trips; identity injected by backend; G-CONTRACT, G-SECURITY |
| P01-T03 | SQLite schema, transaction/migration strategy and synthetic approval/case registry | WAL/FK checks; original bytes immutable; event/ACL producer read by resolver; isolated fixtures; G-SOURCE |
| P01-T04 | Fictional approved old/current SOP, exceptions, drafts, two tenants and cases, policies/timestamps; gold annotation schema | Each golden names required refs/slots/time basis, allowed hypotheses, forbidden actions and disposition; T01–T24 fixtures catalogued; G-CONTRACT |

Exit: deterministic corpus/contracts and exact T01–T24 inventory validated without LLMs;
fixture consistency reviewed and annotation status pilot-only. Offline foundation smoke
uses actual persisted identity/membership/approval and original readers after reopen.
P01 G-SOURCE/G-SECURITY are PARTIAL: indexing/citation API/revocation-after-search remain later.
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
| P04-T01 | Provider-neutral real Groq runtime boundary, four authorized tool facades, nonexclusive preflight and canonical evidence ledger | Server identity cannot be overridden; tools don't bypass domain ACL; multi-tool question stays possible; G-SECURITY, G-BUDGET |
| P04-T02 | Investigation→draft→review boundary→finalization state machine with pre-reserved accounting and global deadline | ≤5 main incl failed/malformed calls, reserve final; tools/retries/cancellation capped; no sixth repair; G-BUDGET |
| P04-T03 | Typed claims, requirement origins, deterministic per-claim eligibility and five dispositions; safe renderer and protected rejected diagnostics | Model answer-kind/hypothesis labels cannot evade risk/requirements; unknown refs and unsupported directives blocked; G-GATE |
| P04-T04 | Message API, citation API, timeline/trace, health/ready, persisted tool failures; synthetic vertical smoke | Authenticated message→verified refs→reader; 5 dispositions; no evidence/tool/conflict paths; G-E2E, G-SECURITY |

Exit verified at E-P04-001: all14 children, actual Groq/HTTP/citation consumers, updated exact-wheel tests and sole end-audit resolution. Passing and failed model runs are retained; no reliability estimate is inferred. Actual Groq end-to-end path and correct abstention proven, under explicit call budgets. Until P06 real critic exists,
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

Exit verified at E-P05-001: allseven children, source/installed/API consumers, actual pilot and sole audit/resolution. Strict pilot model completion0/3 remains a failure measurement, not a runtime reliability claim. A second request preserves reported/observed/hypothesis distinctions without granting
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

Exit: supported exception correction demonstrated with failures preserved; cost, controlled
false objections and retention loss recorded. Semantic/causal false-veto rate remains
unknown under owner-approved ADR0046 and P08 adjudication. Do not claim reliability
from agreement or silently activate adaptive bypass.
P06 exit verified at E-P06-001/002: independent real exact-ID exception recovery and
default-budget generated-draft consumers pass after ADR0062; all six cards and phase-local
gates/audit resolved. Frozen critic matrix retains neutral results and every failure.

## P07 — Optional source-linked graph (Slice 6)

Goal O06. Read all blueprint “Knowledge graph,” “Graph integration only after baseline,”
and graph identity/leak/fan-out hard cases. Depends on P06 and P02 baseline evidence.
Owner: graph, Neo4j storage, graph extraction/expansion and ingest reconciliation; owner-expanded automatic memory promotion/session work below.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| P07-T01 | Verified namespace keys and uniqueness constraints, provisional IDs, reviewed merge audit, typed provenance edges | Concurrent same identity dedupes; same names distinct IDs never merge; G-GRAPH |
| P07-T02 | Optional bounded traversal, canonical neighbor resolution, graph on/off publication requirements and outage behavior | Scope/hops/fan-out/time caps; source recheck before model; required relation unavailable vs optional fallback; G-GRAPH, G-SOURCE |
| P07-T03 | Paired B2/B3 experiment on frozen retrieval corpus, review effort and costs | Recover known missed exception in selected case, evaluate aggregate harm/benefit; record retain/disable decision; G-RESEARCH |
| P07-T04 | Automatic backend memory promotion: sessions, chunk provenance, primary deterministic PathA and cosine/loss PathB | Actual session-local episodic and USER-wide semantic readers; unapproved procedural context; no fifth tool or authority bypass; G-MEMORY/G-SECURITY/G-RESEARCH |

Exit: evidence and cost justify feature state. If no improvement, keep graph disabled and
record negative result; do not fabricate a passing aggregate claim from one showcase.

## P08 — Scientific evaluation, observability and fault injection (Slice 7)

P08 engineering pilot COMPLETE at E-P08-001–003; all12cards verified under approved
pilot boundary.44observations/16errors retained, current T01–T24 controls24PASS, sole
end review and same-reviewer R4 resolution complete. Semantic efficacy and unobserved
candidate-stage metrics remain unknown; see [results](evidence/P08_RESULTS.md).

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

## Atomic execution register

Every path below is repository-relative. Runtime paths are proposed by blueprint “Every
file and its responsibility”; none is created by this planning task. Tests listed with
an owner belong to the same bounded behavior change. Execute dependencies, not file-count
order. Shared-file tasks are sequential. Each proof names the observation that could fail.

### Atomic tasks — P00

#### P00-T04 execution tasks

<a id="p00-t04-01"></a>

- [x] **P00-T04.01 — Ground the task format in Arcana and record the adaptation**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/PROJECT_LEARNING.md`.
  - **Depends:** P00-T03.
  - **Change:** Read representative master-plan tasks and companion documents; record transferable task/proof patterns and retain Palladion scope.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); reference headings explain task size and named consumers without importing Arcana product rules.
  - **Evidence:** E-DOC-002; live Arcana task/rule/reference review and ADR-0009/ADR-0010.

<a id="p00-t04-02"></a>

- [x] **P00-T04.02 — Write file-specific cards for every implementation package**
  - **Files:** `palladion/docs/development/MASTER_DEV_PLAN.md`.
  - **Depends:** P00-T04.01.
  - **Change:** Retain parent IDs and add bounded child tasks with exact paths, dependencies, reader and negative-case proof; keep runtime files planned.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); every implementation package has children and every blueprint responsibility-table file has a planned owner.
  - **Evidence:** E-DOC-002; atomic register and complete 74-file blueprint ownership check.

<a id="p00-t04-03"></a>

- [x] **P00-T04.03 — Enforce the register and synchronize document navigation**
  - **Files:** `palladion/docs/development/check_docs.py`, `palladion/docs/development/TESTING_GATES.md`, `palladion/docs/development/REQUIREMENTS_TRACEABILITY.md`, `palladion/docs/development/PROJECT_MAP.md`, `palladion/docs/development/GOAL.md`, `AGENTS.md`, `palladion/docs/README.md`.
  - **Depends:** P00-T04.02.
  - **Change:** Check child fields, IDs, acyclic dependencies and planned file coverage; update gate/requirement reading links so a future task reaches its card.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); valid register passes; missing files/metadata, dependency cycles and uncovered packages fail checker self-tests.
  - **Evidence:** E-DOC-002; checker CLI and 13 negative controls pass; task/gate links resolve.

<a id="p00-t04-04"></a>

- [x] **P00-T04.04 — Audit and preserve the atomic-plan checkpoint**
  - **Files:** `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/PROJECT_MEMORY.md`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/MASTER_DEV_PLAN.md`.
  - **Depends:** P00-T04.03, P00-T04.05.
  - **Change:** Review task size/order independently; synchronize status and preserve commands, consumer checks, limitations and scoped commit evidence.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); Luna High findings resolved, docs CLI/self-test pass, vision unchanged, no runtime gate closed.
  - **Evidence:** E-DOC-002; independent audit and targeted resolution check completed; final checker passes, scoped documentation checkpoint contains this record.

<a id="p00-t04-05"></a>

- [x] **P00-T04.05 — Tailor useful Arcana development rules into AGENTS**
  - **Files:** `AGENTS.md`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `palladion/docs/development/MASTER_DEV_PLAN.md`.
  - **Depends:** P00-T04.01.
  - **Change:** Adopt the user's requested source-grounding, meaningful-proof, consumer, audit, learning and closeout methods; keep Palladion-specific authority and universal escalation rules.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); source headings/selection recorded; independent review checks no imported UI/runtime/score/approval assumptions or new contradiction.
  - **Evidence:** E-DOC-002; selected Arcana methods tailored into AGENTS and rationale retained in ADR-0010.

#### P00-T05 execution tasks

<a id="p00-t05-01"></a>

- [x] **P00-T05.01 — Record all owner answers in the editable ADR structure**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** P00-T04.04.
  - **Change:** Preserve earlier decisions/history, use Question/Why/Options/Recommendation/What affects what/My answer/Verification, record all accepted directions and exact uv/Groq override without fabricating evidence.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); twelve Q rows resolve to answered ADRs, historical records remain, implementation checks and deferred scope distinguished from owner decisions.
  - **Evidence:** E-DOC-003; all twelve directions recorded, 23 structured ADR records and historical decisions retained.

<a id="p00-t05-02"></a>

- [x] **P00-T05.02 — Align instructions, atomic tasks and goals with the current mandate**
  - **Files:** `AGENTS.md`, `README.md`, `.gitignore`, `palladion/docs/development/MASTER_DEV_PLAN.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/TESTING_GATES.md`, `palladion/docs/development/RESEARCH_PROTOCOL.md`, `palladion/docs/development/PROJECT_MAP.md`.
  - **Depends:** P00-T05.01.
  - **Change:** Require real Groq integration and app-local uv setup after GO; mandate independent pre-phase adversary and one post-phase auditor; preserve operational mocks, budgets and synthetic data.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); no fake-first runtime or optional phase review; both reviewers require the full blueprint and traceable coverage. Product setup/provider calls remain held; only explicitly approved documentation publishing and separate owner/toolchain setup are exceptions. Publish the owner's existing .env/.venv ignore rules unchanged.
  - **Evidence:** E-DOC-003; Groq/uv atomic cards, mandatory reviews and WAIT_FOR_GO propagated.
  - **Amendment evidence:** E-DOC-004; every future reviewer directly reads the full blueprint; owner-authorized docs publishing is distinct from P01 GO. Existing ignored user environment is verified, not a closed package-setup task.

<a id="p00-t05-03"></a>

- [x] **P00-T05.03 — Validate ADR answer structure and synchronize all development records**
  - **Files:** `palladion/docs/development/check_docs.py`, `palladion/docs/README.md`, `palladion/docs/development/REQUIREMENTS_TRACEABILITY.md`, `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/PROJECT_MEMORY.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** P00-T05.02.
  - **Change:** Check structured ADR fields and accepted answers, Q/ADR links, atomic metadata and mandatory review protocol; preserve historical evidence and explicit WAIT_FOR_GO state. P00 alone may own existing root README/.gitignore publishing artifacts; negative controls reject unrelated root paths and runtime ownership of root navigation.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); positive checker and deliberately missing question/impact/answer tests pass/fail correctly; all doc links and file owners resolve.
  - **Evidence:** E-DOC-003; both checker commands pass, including 17 negative controls and current link/file coverage.
  - **Amendment evidence:** E-DOC-004; final checker/CLI passes 20 negative controls, narrow P00 root-file ownership, current records reconciled and historical results retained.

<a id="p00-t05-04"></a>

- [x] **P00-T05.04 — Complete coordinator and independent whole-suite vision audits**
  - **Files:** `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/PROJECT_MEMORY.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/MASTER_DEV_PLAN.md`.
  - **Depends:** P00-T05.03.
  - **Change:** After document gates, coordinator and one GPT 6 Luna High work auditor each check every development document against the full blueprint and user amendments; resolve findings, record evidence, checkpoint docs and stop for GO.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); per-document coverage/full-vision audit receipts, findings and resolutions retained; no product/research gate or live account success claimed.
  - **Evidence:** E-DOC-003; coordinator and single Luna High auditor checked all twelve development docs/full blueprint; all three audit findings resolved and rechecked; 18 negative controls pass. Documentation checkpoint only; WAIT_FOR_GO.
  - **Amendment evidence:** E-DOC-004; fresh pre/post full-blueprint reviews and same-auditor status-resolution verification complete. Coordinator clarified residual historical wording and synchronized D07/P00/G-DOC. Documentation-only main publishing approved; P01 remains WAIT_FOR_GO.

### Atomic tasks — P01

#### P01-T01 execution tasks

<a id="p01-t01-01"></a>

- [x] **P01-T01.01 — Apply the accepted synthetic approval contract**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** P00-T05.04.
  - **Change:** Read accepted ADR-0012 and map authenticated synthetic administrator events, separate uploader/approver grants and source checks into the implementation contract; do not reopen the answered choice.
  - **Proof:** DOC; [G-DOC](TESTING_GATES.md#g-doc-task-coverage); source metadata/registry/access consumers and negative self-approval case are specified under the accepted answer.
  - **Evidence:** E-P01-001; Stored trusted administrator approval, separate actors/grants and negative self-approval are exercised through Registry; ADR-0012 direction unchanged. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t01-02"></a>

- [x] **P01-T01.02 — Establish the uv environment, package and validation tooling**
  - **Files:** `palladion/.gitignore`, `palladion/.gitattributes`, `palladion/pyproject.toml`, `palladion/uv.lock`, `palladion/src/evidence_agent/__init__.py`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/check_docs.py`.
  - **Depends:** P00-T05.04.
  - **Change:** After explicit GO, verify uv and the existing user-created .venv inside C:/palladion/palladion; reuse it when compatible rather than recreate it. Select compatible Python/tooling/packages under delegated authority, pin uv.lock, and expose package version. Preserve original fixture bytes across Git checkouts using app .gitattributes. Verify .venv/ protection before reuse or creation; own app-local .gitignore protection and preserve the root ignore rules. If absent, create the environment with uv venv only after protection is proven. Baseline gets a separate environment later.
  - **Proof:** SMOKE; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); uv version, app-local environment/import and configured validation commands run; git check-ignore proves app .venv protection before reuse or creation and locked sync is reproducible; no secret needed for setup.
  - **Evidence:** E-P01-001; Existing uv environment reused; locked sync, version import, sdist/wheel and fresh non-editable/exact-wheel reader smoke pass. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t01-03"></a>

- [x] **P01-T01.03 — Validate Groq settings and explicit model enablement**
  - **Files:** `palladion/src/evidence_agent/settings.py`, `palladion/config/settings.yaml`, `palladion/.env.example`, `palladion/.gitignore`, `palladion/tests/test_goldens.py`, `palladion/tests/test_settings.py`.
  - **Depends:** P01-T01.02.
  - **Change:** Load typed budgets and explicit live-call flags; select provider groq/model qwen/qwen3.8-27b per ADR-0013. Provide non-secret root .env loading instructions and ignore .venv/databases/traces. Key presence alone never enables requests.
  - **Proof:** UNIT; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); valid selected-model config loads; invalid/unknown config fails, disabled live flag denies dispatch despite credentials; root key never copied into app env/template.
  - **Evidence:** E-P01-001; Twelve settings checks verify selected Groq config, unknown/type/budget rejection and disabled dispatch despite credential availability flag; no key loaded. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t01-04"></a>

- [x] **P01-T01.04 — Document runnable development commands and safety boundaries**
  - **Files:** `palladion/README.md`.
  - **Depends:** P01-T01.03.
  - **Change:** Publish actual uv venv, locked install/check/start commands from the app directory, repository-root credential loading and explicit Groq enablement; distinguish synthetic operational fixtures from the real model API.
  - **Proof:** SMOKE; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); run documented package/check commands in isolated environment; no absent secret or unavailable entry point assumed.
  - **Evidence:** E-P01-001; README commands and offline entry point run from the app directory; isolated installed-wheel reader proves packaged schema resource consumption. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

#### P01-T02 execution tasks

<a id="p01-t02-01"></a>

- [x] **P01-T02.01 — Define identity, evidence and typed error envelopes**
  - **Files:** `palladion/src/evidence_agent/core/models.py`, `palladion/src/evidence_agent/core/errors.py`, `palladion/tests/test_goldens.py`, `palladion/tests/test_contracts.py`.
  - **Depends:** P01-T01.02.
  - **Change:** Define Principal, EvidenceRecord, source references and result/error envelopes with schema versions; store/tool readers retain types and provenance.
  - **Proof:** UNIT; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); valid round-trip preserves fields; invalid enums/extras and naive required timestamps rejected.
  - **Evidence:** E-P01-001; Strict versioned envelope round trips and invalid enum/extra/naive-time rejection pass in test_contracts. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t02-02"></a>

- [x] **P01-T02.02 — Define claims, decisions, observations, packets and reviews**
  - **Files:** `palladion/src/evidence_agent/core/models.py`, `palladion/tests/test_goldens.py`, `palladion/tests/test_contracts.py`.
  - **Depends:** P01-T02.01.
  - **Change:** Add typed ClaimDraft, requirement origins, PolicyDecision, LiveObservation, packet, CriticReview and GateDecision shapes for later domain consumers.
  - **Proof:** UNIT; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); observed/reported/hypothesis distinctions survive serialization; missing provenance and invalid dispositions fail.
  - **Evidence:** E-P01-001; Blueprint status/time-basis vocabulary, policy selection/trace prerequisites, reported/observed/hypothesis and packet/gate shapes verified by contract tests; later engines remain unbuilt. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t02-03"></a>

- [x] **P01-T02.03 — Implement canonical source and namespace-scoped IDs**
  - **Files:** `palladion/src/evidence_agent/core/ids.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_graph_identity.py`.
  - **Depends:** P01-T02.01.
  - **Change:** Derive stable revision/chunk/reference IDs from explicit identity and namespace; registry/search/graph later consume the same IDs.
  - **Proof:** UNIT; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); same immutable inputs repeat IDs, changed tenant/revision does not collide, label similarity cannot determine identity.
  - **Evidence:** E-P01-001; Stable tenant/revision/span and verified/provisional identity tests pass; Registry consumes canonical digest/revision helpers. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t02-04"></a>

- [x] **P01-T02.04 — Establish backend principal and case authorization**
  - **Files:** `palladion/src/evidence_agent/security/access.py`, `palladion/tests/test_security.py`.
  - **Depends:** P01-T02.01.
  - **Change:** Implement synthetic principal/membership/grant checks for domain callers; model and packet identity fields cannot widen request scope.
  - **Proof:** UNIT; [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); authorized operation passes; wrong tenant/case/role, swapped identity and revoked grants denied without existence leak.
  - **Evidence:** E-P01-001; Current stored profile/membership callbacks consumed by Registry/CLI; tampered identity, wrong scope/grants/roles and revocation denied. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

#### P01-T03 execution tasks

<a id="p01-t03-01"></a>

- [x] **P01-T03.01 — Define registry, case-membership and audit persistence**
  - **Files:** `palladion/src/evidence_agent/storage/schema.sql`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P01-T01.01, P01-T02.02, P01-T02.03.
  - **Change:** Define blueprint registry/chunk/policy/event/memory/manifest/audit tables plus memberships/keys; store schema versions and consistent UTC semantics.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); temporary SQLite accepts valid references and rejects invalid FK/status relationships; no existing database reset.
  - **Evidence:** E-P01-001; Temporary SQLite enforces registry/status/FK/approval relationships; domain Registry consumes persisted principals/memberships/approvals. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t03-02"></a>

- [x] **P01-T03.02 — Own SQLite connections, transactions and upgrades**
  - **Files:** `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P01-T03.01.
  - **Change:** Apply WAL/FK and transactional initialization/upgrades under approved migration strategy; production connection reader reopens stored data.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); fresh schema initializes, successful populated upgrade preserves rows, close/reopen preserves fixture rows, failed upgrade rolls back; all tests use isolated temporary files.
  - **Evidence:** E-P01-001; Fresh initialization, populated upgrade, failed transactional upgrade rollback, reopen and unchanged foreign/newer rejection tested on isolated files. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t03-03"></a>

- [x] **P01-T03.03 — Implement write-once originals and verified range reads**
  - **Files:** `palladion/src/evidence_agent/storage/originals.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P01-T03.02, P01-T02.03.
  - **Change:** Store immutable content-addressed bytes and exact range reads consumed later by citation resolver rather than model summaries.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); readback hash/bytes match, overwrite/path escape/corrupt range fails without replacing previously cited content.
  - **Evidence:** E-P01-001; Write-once SHA objects and exact byte/range readers pass corruption/escape/invalid-range/idempotency tests; approved CLI readbacks survive reopen. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

#### P01-T04 execution tasks

<a id="p01-t04-01"></a>

- [x] **P01-T04.01 — Author synthetic SOP revisions, exception and draft**
  - **Files:** `palladion/data/demo/sop_2025.md`, `palladion/data/demo/sop_2026.md`, `palladion/data/demo/exception_appendix.md`, `palladion/data/demo/draft_memo.md`.
  - **Depends:** P01-T01.01, P01-T02.03.
  - **Change:** Write consistent fictional historical/current clauses, explicit exception and persuasive unapproved memo; approval remains outside document prose.
  - **Proof:** DOC; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); reviewer traces expected clauses; draft/old-only text cannot receive a gold current-authorization label.
  - **Evidence:** E-P01-001; Four fictional source originals have validated clause byte spans/hashes and external approval metadata; draft remains unapproved. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t04-02"></a>

- [x] **P01-T04.02 — Author case, policy and changing-observation fixtures**
  - **Files:** `palladion/data/demo/sample_cases.json`, `palladion/config/policies/demo_reversal_v2.json`, `palladion/tests/test_goldens.py`.
  - **Depends:** P01-T04.01, P01-T02.02.
  - **Change:** Define two tenants/roles/cases, trusted/untrusted times, synthetic policy and mock snapshots for policy/live readers.
  - **Proof:** UNIT; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); valid fixtures resolve intended clauses; unknown source/time field and contradictory fixture assumptions fail validation.
  - **Evidence:** E-P01-001; Two tenants, three cases/seven principals and seven timestamped/changing observations resolve valid policy/source references; malformed fields and impossible expectations rejected. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

<a id="p01-t04-03"></a>

- [x] **P01-T04.03 — Validate gold labels and adversarial fixture inventory**
  - **Files:** `palladion/data/demo/goldens.jsonl`, `palladion/src/evidence_agent/core/fixtures.py`, `palladion/scripts/validate_foundation.py`, `palladion/tests/test_goldens.py`.
  - **Depends:** P01-T04.02.
  - **Change:** Encode scope, exact clauses, slots/time basis, policy/disposition, hypotheses and forbidden actions; catalog T01–T24 for evaluator.
  - **Proof:** UNIT; [G-CONTRACT](TESTING_GATES.md#g-contract-task-coverage); every gold reference resolves, exact T01–T24 occur once; missing cases/labels, impossible expected answers and duplicate IDs fail. Offline CLI consumes real registry/source readers; annotation limits recorded.
  - **Evidence:** E-P01-001; Exact T01–T24 once; missing/duplicate cases, wrong references/scopes/times and impossible answer labels rejected. PILOT only; independent research adjudication deferred. Single work audit and resolution verified at E-P01-001; broader multi-phase gates remain partial.

### Atomic tasks — P02

#### P02-T01 execution tasks

<a id="p02-t01-01"></a>

- [x] **P02-T01.01 — Parse MD/TXT into source-preserving structures**
  - **Files:** `palladion/src/evidence_agent/ingest/parsing.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P01-T04.03.
  - **Change:** Parse UTF-8 headings/tables/clauses with original offsets and lines; chunker consumes exact text and parser version.
  - **Proof:** UNIT; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); spans reconstruct Unicode originals; malformed/unsupported input returns explicit failure, not fabricated text.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t01-02"></a>

- [x] **P02-T01.02 — Chunk without detaching rule exceptions**
  - **Files:** `palladion/src/evidence_agent/ingest/chunking.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P02-T01.01, P01-T02.03.
  - **Change:** Produce deterministic chunks and parent/neighbor links; separate original citation text from generated embedding prefixes.
  - **Proof:** UNIT; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); rule/exception boundary is recoverable, IDs/order/hash stable, contextual prefix never enters original quote.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t01-03"></a>

- [x] **P02-T01.03 — Validate trusted approval and upload metadata**
  - **Files:** `palladion/src/evidence_agent/ingest/metadata.py`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_security.py`.
  - **Depends:** P01-T03.03, P01-T02.04.
  - **Change:** Check uploader/approver grants, MIME/size/hash, temporal scope and supersession before pipeline writes authenticated registry metadata.
  - **Proof:** UNIT; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); valid upload accepted; prose approval, unauthorized approver and invalid supersession scope rejected.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t01-04"></a>

- [x] **P02-T01.04 — Publish only reconciled ingest generations**
  - **Files:** `palladion/src/evidence_agent/ingest/pipeline.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/schema.sql`, `palladion/src/evidence_agent/core/retrieval.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P02-T01.02, P02-T01.03, P02-T02.02.
  - **Change:** Stage sources/chunks/backend acknowledgments; publish SQLite generation only after exact manifest reconciliation; retry accepted input idempotently. Owner-approved additive v3 migration persists exact IDs/hashes and representation fingerprints; prove fresh/populated/failed upgrades.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); interrupted/partial upsert stays unpublishable, recovery idempotent, graph-off required-index set explicit.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

#### P02-T02 execution tasks

<a id="p02-t02-01"></a>

- [x] **P02-T02.01 — Pin and probe dense/BM25 retrieval dependencies**
  - **Files:** `palladion/compose.yaml`, `palladion/scripts/qdrant_server.py`, `palladion/scripts/probe_retrieval.py`, `palladion/pyproject.toml`, `palladion/config/settings.yaml`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P01-T01.03.
  - **Change:** Resolve Q03/Q04 using official pinned APIs and actual probe; configure synthetic local Qdrant, model/tokenizer and BM25 mode for adapter. User authorizes a Docker alternative; checksum-pinned standalone Qdrant in WSL with Linux-owned storage is the supported path on this machine.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); real server/client supports named vectors and native RRF k=60; incompatible mode fails visibly instead of switching weighting.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t02-02"></a>

- [x] **P02-T02.02 — Implement Qdrant collection, points and scoped queries**
  - **Files:** `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P02-T02.01, P01-T02.03.
  - **Change:** Create payload indexes before ingestion and shared dense/bm25 point IDs; expose scoped upsert/query/health for pipeline and hybrid readers.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); actual collection readback includes both representations/filters; missing vector or generation is not trusted as READY.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

#### P02-T03 execution tasks

<a id="p02-t03-01"></a>

- [x] **P02-T03.01 — Resolve exact identifiers without fuzzy substitution**
  - **Files:** `palladion/src/evidence_agent/storage/exact.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P01-T03.02, P01-T02.03.
  - **Change:** Map validated exact codes/aliases to canonical targets; hybrid reader unions results separately from ranking fusion.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); known exact ID resolves, unknown stays unknown, POL-17 never silently returns POL-71; namespace filter enforced.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t03-02"></a>

- [x] **P02-T03.02 — Resolve eligible immutable evidence before exposure**
  - **Files:** `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_security.py`.
  - **Depends:** P02-T01.03, P01-T03.03, P01-T02.04.
  - **Change:** Recheck ACL, publication generation, approval/time/scope and exact span/hash; citation and final gate share canonical resolver.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); valid span readback passes; draft/revoked/stale-index/restricted/corrupt hit blocked before prompt or output.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t03-03"></a>

- [x] **P02-T03.03 — Fuse dense/sparse once and union exact candidates**
  - **Files:** `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P02-T02.02, P02-T03.01, P02-T03.02.
  - **Change:** Run scoped dense/BM25 queries, native RRF exactly once, exact injection and canonical eligibility before rerank reader.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); relevant/wrong-ID/old-source cases and sparse outage classified; score never becomes truth probability or exhaustive absence.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t03-04"></a>

- [x] **P02-T03.04 — Rerank and expand parent/exception context**
  - **Files:** `palladion/src/evidence_agent/retrieval/rerank.py`, `palladion/config/settings.yaml`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P02-T03.03.
  - **Change:** Add explicit rerank/no-op treatment and bounded original parent/neighbor expansion; assembly rechecks expanded spans and deduplicates sources.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); exception recovered within passage budget; restricted adjacent text excluded, duplicates cannot consume all slots.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t03-05"></a>

- [x] **P02-T03.05 — Report searched scope, required slots and index health**
  - **Files:** `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P02-T03.04.
  - **Change:** Build search-result provenance, partial failures and supplied-source coverage distinct from inventory attestation for agent/evaluator readers.
  - **Proof:** UNIT; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage); accepted-but-unindexed revision warns; zero hits cannot certify missing external inventory or required-slot sufficiency.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

#### P02-T04 execution tasks

<a id="p02-t04-01"></a>

- [x] **P02-T04.01 — Wire source and citation API entry points**
  - **Files:** `palladion/src/evidence_agent/main.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/scripts/serve.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P02-T01.04, P02-T03.05.
  - **Change:** Add app factory/lifespan and authenticated upload/separate approval/search/revocation/index-health/evidence-read transport with real domain adapters.
  - **Proof:** SMOKE; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); API upload/approve/search/citation reads exact original; unauthorized self-approval and citation read denied.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t04-02"></a>

- [x] **P02-T04.02 — Record minimal correlated retrieval audit events**
  - **Files:** `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/tests/test_security.py`.
  - **Depends:** P02-T04.01.
  - **Change:** Persist generation, safe scope, stage counts/timing, exclusion reasons and failure IDs through audit.py's internal append/read interface. P04-T04.02 later exposes the role-gated API reader; its authorization is not claimed here.
  - **Proof:** INTEGRATION; [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); production audit append→close/reopen→internal readback preserves matched trace/result; restricted-text/credential canaries absent on success/error. API authorization proof remains P04-T04.02.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t04-03"></a>

- [x] **P02-T04.03 — Expose idempotent seed and reconciliation commands**
  - **Files:** `palladion/scripts/reconcile.py`, `palladion/scripts/seed.py`, `palladion/src/evidence_agent/core/bootstrap.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P02-T04.02.
  - **Change:** Seed synthetic accepted sources and compare manifest IDs/counts/hashes through real adapters; existing volumes are never reset by default.
  - **Proof:** SMOKE; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); second seed preserves IDs, missing point is detected, citation still resolves; no destructive default.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

<a id="p02-t04-04"></a>

- [x] **P02-T04.04 — Measure B0/B1/B2 retrieval before agent and graph**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_goldens.py`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** P02-T04.03.
  - **Change:** Run pinned lexical/hybrid/rerank retrieval-only substrate pilot per-stage queries including ANN-vs-exact and language/time/ACL slices; scorer consumes actual ranked references.
  - **Proof:** MEASUREMENT; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); wrong expected clause fails scoring; preserve pilot counts/failures with no invented target or held-out tuning.
  - **Evidence:** E-P02-001 task-to-consumer index and exact commands/results; single work audit and all four finding resolutions verified; P02 closed. Later runtime/graph/research obligations are not passed.

### Atomic tasks — P03

#### P03-T01 execution tasks

<a id="p03-t01-01"></a>

- [x] **P03-T01.01 — Register approved policies and source-clause eligibility**
  - **Files:** `palladion/src/evidence_agent/policy/registry.py`, `palladion/src/evidence_agent/policy/bootstrap.py`, `palladion/tests/conftest.py`, `palladion/tests/test_policy_engine.py`.
  - **Depends:** P02-T04.04.
  - **Change:** Read approved family/version/source links under principal scope; validate rule metadata and preserve current/historical selection inputs for temporal resolver.
  - **Proof:** INTEGRATION; [G-POLICY](TESTING_GATES.md#g-policy-task-coverage); valid table loads; unapproved/missing/revoked current clause cannot create policy authority.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t01-02"></a>

- [x] **P03-T01.02 — Resolve four trusted time bases and half-open intervals**
  - **Files:** `palladion/src/evidence_agent/policy/temporal.py`, `palladion/tests/test_policy_temporal.py`.
  - **Depends:** P03-T01.01.
  - **Change:** Obtain policy-declared time from permitted live/case/clock/domain sources; selection uses valid intervals without revision-name ranking.
  - **Proof:** UNIT; [G-TEMPORAL](TESTING_GATES.md#g-temporal-task-coverage); all bases/exact boundaries select correctly; missing/untrusted/naive time cannot select convenient version.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t01-03"></a>

- [x] **P03-T01.03 — Apply supersession, conflicts and historical cutoffs**
  - **Files:** `palladion/src/evidence_agent/policy/temporal.py`, `palladion/src/evidence_agent/policy/registry.py`, `palladion/tests/test_policy_temporal.py`.
  - **Depends:** P03-T01.02, P03-T01.04.
  - **Change:** Apply authorized scope-matching edges and knowledge_cutoff; preserve audit semantics and reject incomparable overlaps or mixed-basis definitions.
  - **Proof:** INTEGRATION; [G-TEMPORAL](TESTING_GATES.md#g-temporal-task-coverage); T02/T03/T21 and concurrent overlap writes cannot silently choose winner; undefined migration remains conflict.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t01-04"></a>

- [x] **P03-T01.04 — Apply accepted historical-audit and migration semantics**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`, `palladion/tests/test_policy_temporal.py`.
  - **Depends:** P03-T01.02.
  - **Change:** Apply accepted ADR-0016/Q05: record concrete synthetic knowledge-cutoff audit fixtures and trace-retention scope; incompatible time-basis migration remains conflict unless explicit approved precedence exists. No repeated policy vote or invented real-business rule.
  - **Proof:** DOC; [G-TEMPORAL](TESTING_GATES.md#g-temporal-task-coverage); accepted decision and boundary fixtures distinguish historical knowledge/current revocation; no inferred retroactive authorization.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

#### P03-T02 execution tasks

<a id="p03-t02-01"></a>

- [x] **P03-T02.01 — Validate and execute the bounded predicate AST**
  - **Files:** `palladion/src/evidence_agent/policy/engine.py`, `palladion/src/evidence_agent/core/models.py`, `palladion/tests/test_policy_engine.py`.
  - **Depends:** P03-T01.03.
  - **Change:** Implement typed allowlisted comparison/all/any/not operators with depth/work bounds; required-field validation precedes predicate execution.
  - **Proof:** UNIT; [G-POLICY](TESTING_GATES.md#g-policy-task-coverage); valid rows match; unknown type/operator, missing fact and excessive recursion fail; no eval/exec/SQL path.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t02-02"></a>

- [x] **P03-T02.02 — Produce evidence-linked policy decision traces**
  - **Files:** `palladion/src/evidence_agent/policy/engine.py`, `palladion/src/evidence_agent/policy/registry.py`, `palladion/src/evidence_agent/policy/bootstrap.py`, `palladion/tests/conftest.py`, `palladion/tests/test_policy_engine.py`.
  - **Depends:** P03-T02.01, P03-T03.02.
  - **Change:** Validate fact provenance and intended-use freshness; return selected version/basis/as-of/inputs/rows/source clauses/audit result for a direct domain replay reader; P04 gate consumption remains deferred.
  - **Proof:** INTEGRATION; [G-POLICY](TESTING_GATES.md#g-policy-task-coverage); replay trace; missing settlement is INCOMPLETE_INPUT, unverified fact is not false, conflicting rows cannot grant eligibility.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

#### P03-T03 execution tasks

<a id="p03-t03-01"></a>

- [x] **P03-T03.01 — Define named operation and timestamp contracts**
  - **Files:** `palladion/src/evidence_agent/live/contracts.py`, `palladion/config/adapters.yaml`, `palladion/tests/test_live.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P03-T01.03.
  - **Change:** Apply ADR-0018/Q07; record explicit synthetic owner/rule freshness limits, validate operation versions/bounds/errors and all three timestamp meanings; values are fixture assumptions, not inferred company policy.
  - **Proof:** UNIT; [G-LIVE](TESTING_GATES.md#g-live-task-coverage); valid envelope preserves three times; unknown operation/extra URL/invalid identifier/schema rejected before adapter call.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t03-02"></a>

- [x] **P03-T03.02 — Provide deterministic observations and failure fixtures**
  - **Files:** `palladion/src/evidence_agent/live/mock.py`, `palladion/tests/test_live.py`.
  - **Depends:** P03-T03.01.
  - **Change:** Implement fictional transaction/settlement/incident and optional BI reads with changing snapshots and timeout/throttle/schema/denied/not-found cases.
  - **Proof:** UNIT; [G-LIVE](TESTING_GATES.md#g-live-task-coverage); repeatable fixtures preserve owning system/times; old data_as_of remains stale despite fresh read and NOT_FOUND stays scoped.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t03-03"></a>

- [x] **P03-T03.03 — Authorize target-bound read-only gateway calls**
  - **Files:** `palladion/src/evidence_agent/live/gateway.py`, `palladion/src/evidence_agent/security/access.py`, `palladion/tests/test_live.py`, `palladion/tests/test_security.py`.
  - **Depends:** P03-T03.02.
  - **Change:** Map backend principal/case to permitted operations/targets; minimize/redact output before ledger; model never supplies credentials/host/write verbs.
  - **Proof:** INTEGRATION; [G-LIVE](TESTING_GATES.md#g-live-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); authorized target passes; cross-case merchant and dynamic SQL/URL/write denied without existence leak.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

<a id="p03-t03-04"></a>

- [x] **P03-T03.04 — Bound live retries, deduplication and failure audit**
  - **Files:** `palladion/src/evidence_agent/live/gateway.py`, `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/tests/test_live.py`.
  - **Depends:** P03-T03.03, P03-T02.02.
  - **Change:** Apply deadlines/response/rate limits and single retry owner; deduplicate identical in-flight reads and classify failures for gate consumer.
  - **Proof:** INTEGRATION; [G-LIVE](TESTING_GATES.md#g-live-task-coverage); transient retry stays capped, permission/schema failure never broadens scope, cancellation stops read and audit preserves timestamps/errors.
  - **Evidence:** E-P03-001 task-to-consumer proof and current validations; single work audit and status-finding resolution complete.

### Atomic tasks — P04

#### P04-T01 execution tasks

<a id="p04-t01-01"></a>

- [x] **P04-T01.01 — Implement and probe the real Groq model boundary**
  - **Files:** `palladion/src/evidence_agent/agent/llm.py`, `palladion/tests/test_agent_budget.py`, `palladion/tests/test_llm_transport.py`, `palladion/scripts/validate_agent.py`.
  - **Depends:** P03-T03.04.
  - **Change:** Implement provider-neutral result/error/usage handling backed by Groq qwen/qwen3.8-27b. Explicitly enabled commands load the existing root .env without exposing it; verify tool/schema/account capabilities before downstream live integration. No fake runtime or silent alternate model.
  - **Proof:** INTEGRATION; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); a bounded real Groq request proves tool/draft/final transport capabilities as applicable; malformed/timeout data fixtures exercise accounting separately. Rate/access failure blocks provider proof, not a substituted success.

<a id="p04-t01-02"></a>

- [x] **P04-T01.02 — Hydrate minimal case state and current evidence ledger**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/memory/packet.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_memory.py`, `palladion/tests/__init__.py`.
  - **Depends:** P04-T01.01.
  - **Change:** Read authorized events into packet skeleton/current-request ledger; preserve reported/observed distinction for preflight/four-tool readers.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); reopen hydrates same case, wrong case denied; old handle remains pointer until source revalidation.

<a id="p04-t01-03"></a>

- [x] **P04-T01.03 — Define and dispatch exactly four read tools**
  - **Files:** `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/agent/services.py`, `palladion/src/evidence_agent/agent/search_worker.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/retrieval/rerank.py`, `palladion/tests/test_search_worker.py`, `palladion/tests/test_security.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P04-T01.02.
  - **Change:** Expose knowledge/policy/live/memory schemas only; inject server identity, validate limits and call implemented domain readers.
  - **Proof:** INTEGRATION; [G-SECURITY](TESTING_GATES.md#g-security-task-coverage), [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); four valid calls read domain results; arbitrary network/SQL/approval/payment/identity overrides rejected.

<a id="p04-t01-04"></a>

- [x] **P04-T01.04 — Produce nonexclusive deterministic preflight hints**
  - **Files:** `palladion/src/evidence_agent/agent/preflight.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P04-T01.03.
  - **Change:** Hydrate packet/detect IDs and optionally prefetch bounded authorized evidence; hints cannot restrict later authorized tool selection.
  - **Proof:** UNIT; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); greeting skips fetch, mixed question retains grants, zero hits/outage never asserts exhaustive absence or broadens target.

#### P04-T02 execution tasks

<a id="p04-t02-01"></a>

- [x] **P04-T02.01 — Account model and tool attempts before dispatch**
  - **Files:** `palladion/src/evidence_agent/agent/loop.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P04-T01.04.
  - **Change:** Atomically reserve/consume main/critic/tool attempts across parallel dispatch/retries/failures; keep one of five main slots for finalization.
  - **Proof:** UNIT; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); timeout/invalid JSON/races never create free calls; fourth exploration stops, fifth final and forbidden sixth exercised.

<a id="p04-t02-02"></a>

- [x] **P04-T02.02 — Wire investigation, draft and unavailable-review boundary**
  - **Files:** `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/draft.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P04-T02.01.
  - **Change:** Drive actual Groq model to tools, ledger, draft, review boundary and reserved final. Until P06 the critic absence is explicitly unavailable; deterministic invalid-result fixtures only test failure guards, never substitute runtime proof.
  - **Proof:** INTEGRATION; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage), [G-GATE](TESTING_GATES.md#g-gate-task-coverage); normal draft finalizes, absent draft yields safe partial, unavailable review cannot authorize operational answer.

<a id="p04-t02-03"></a>

- [x] **P04-T02.03 — Stop and persist work on deadline or cancellation**
  - **Files:** `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/memory/store.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P04-T02.02.
  - **Change:** Propagate deadline/cancellation to model/tools; persist completed results and explicit errors for next authorized request.
  - **Proof:** INTEGRATION; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); slow parallel work terminates under cap, no detached invocation continues, resumed reader sees attempt status.

#### P04-T03 execution tasks

<a id="p04-t03-01"></a>

- [x] **P04-T03.01 — Validate claim drafts and requirement origins**
  - **Files:** `palladion/src/evidence_agent/agent/draft.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/tests/test_gate.py`.
  - **Depends:** P04-T02.02.
  - **Change:** Validate claim/evidence IDs and policy-required slots independently of model suggestions; preserve hypotheses and precise missing requirements for gate.
  - **Proof:** UNIT; [G-GATE](TESTING_GATES.md#g-gate-task-coverage); valid associations accepted, invented ref/omitted slot and action relabeled hypothesis cannot evade requirements.

<a id="p04-t03-02"></a>

- [x] **P04-T03.02 — Apply per-claim deterministic eligibility checks**
  - **Files:** `palladion/src/evidence_agent/agent/gate.py`, `palladion/tests/test_gate.py`.
  - **Depends:** P04-T03.01, P04-T03.04.
  - **Change:** Revalidate evidence/source/time/ACL, rule trace, freshness and critical challenges under actual claims before release; semantic inadequacy stays qualified. Owner-approved ADR-0034 adds canonical temporal-input provenance in core/models.py and policy/engine.py; implement and verify the owning producer, not a second authority store.
  - **Proof:** INTEGRATION; [G-GATE](TESTING_GATES.md#g-gate-task-coverage); supported informational fixture passes; stale/revoked/wrong-scope/unrelated citation and missing rule input block material claim.

<a id="p04-t03-03"></a>

- [x] **P04-T03.03 — Render five dispositions and deterministic fallback**
  - **Files:** `palladion/src/evidence_agent/agent/gate.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/tests/test_gate.py`.
  - **Depends:** P04-T03.02.
  - **Change:** Render gate-owned verified claims, scoped gaps/conflicts/hypotheses/citations; malformed final output or budget exhaustion invokes safe template.
  - **Proof:** UNIT; [G-GATE](TESTING_GATES.md#g-gate-task-coverage); five outcomes preserve reasons; fallback never repeats blocked directive, leaks protected diagnostic or calls a sixth model turn.

<a id="p04-t03-04"></a>

- [x] **P04-T03.04 — Apply the accepted support rubric and escalation boundary**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`, `palladion/data/demo/goldens.jsonl`.
  - **Depends:** P04-T03.01.
  - **Change:** Apply ADR-0020/Q09: record concrete independently reviewed support/exception rubric and authorized human escalation assignment before consequential supported demonstrations. If assignment/labels unavailable, adequacy remains qualified rather than imaginary approval.
  - **Proof:** DOC; [G-GATE](TESTING_GATES.md#g-gate-task-coverage); authorized criteria distinguish valid but irrelevant citation, unsupported operational directive and unresolved critical challenge; no claim of complete semantic proof.

#### P04-T04 execution tasks

<a id="p04-t04-01"></a>

- [x] **P04-T04.01 — Wire authenticated messages into the runtime**
  - **Files:** `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/main.py`, `palladion/tests/test_end_to_end.py`, `palladion/tests/test_runtime_api.py`, `palladion/scripts/serve.py`, `palladion/scripts/seed.py`.
  - **Depends:** P04-T03.03, P04-T02.03.
  - **Change:** Inject real services into message endpoint and return gate-owned response; persist attempts/outcomes for later continuity reader.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage); synthetic HTTP request consumes real tools/ledger/gate and returned citations read back; denied case/tool failure safe.

<a id="p04-t04-02"></a>

- [x] **P04-T04.02 — Expose authorized timeline, traces and health**
  - **Files:** `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/src/evidence_agent/main.py`, `palladion/tests/test_runtime_api.py`, `palladion/tests/test_end_to_end.py`, `palladion/tests/test_security.py`.
  - **Depends:** P04-T04.01, P02-T04.02.
  - **Change:** Read persisted case/audit events with role redaction; report health/readiness of required dependencies without conflating liveness and successful verification.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); reader sees persisted result, ordinary operator denied developer trace, dependency outage leaks no config or false success.

<a id="p04-t04-03"></a>

- [x] **P04-T04.03 — Prove the real Groq answer walkthrough**
  - **Files:** `palladion/tests/test_end_to_end.py`, `palladion/tests/test_goldens.py`, `palladion/scripts/validate_agent.py`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** P04-T04.02.
  - **Change:** Exercise actual Groq-backed supported information, missing-settlement partial, conflict, scoped no-evidence and unavailable paths through HTTP and real evidence reader. Keep deterministic pure guard tests separate from real-provider smoke records.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-GATE](TESTING_GATES.md#g-gate-task-coverage); T09/T22 never authorize reversal; no-tool/invalid-model paths retain useful gaps; task processes/ports verified stopped.

### Atomic tasks — P05

#### P05-T01 execution tasks

<a id="p05-t01-01"></a>

- [x] **P05-T01.01 — Persist scoped memory categories and failed attempts**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/memory_schema.sql`, `palladion/src/evidence_agent/security/access.py`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_memory.py`.
  - **Depends:** P04-T04.03.
  - **Change:** Expand event store into episodic/semantic/procedural entries with USER/CASE/TEAM/ORGANIZATION scope and attributable source/event refs for recall.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); close/reopen preserves labels/failures; cross-case read and unsupported guess promotion denied.

<a id="p05-t01-02"></a>

- [x] **P05-T01.02 — Control fact validity and semantic promotion**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/scripts/memory.py`, `palladion/tests/test_memory.py`, `palladion/tests/test_security.py`.
  - **Depends:** P05-T01.01.
  - **Change:** Apply authorized user/owner validity/revocation and explicit organization promotion; retain actor/time/rule without model expiry decisions.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); no expiry stays UNSPECIFIED, correction auditable, repeated assertion cannot become global policy.

#### P05-T02 execution tasks

<a id="p05-t02-01"></a>

- [x] **P05-T02.01 — Read structured/FTS memory under current principal**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_memory.py`.
  - **Depends:** P05-T01.02.
  - **Change:** Implement typed/exact/FTS recall and feed attributable facts/events to recall_memory; vector augmentation remains disabled until measured.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); authorized known fact recalled with source, similar private case excluded, stale principal grants not inherited.

<a id="p05-t02-02"></a>

- [x] **P05-T02.02 — Generate bounded packets from actual case events**
  - **Files:** `palladion/src/evidence_agent/memory/packet.py`, `palladion/src/evidence_agent/settings.py`, `palladion/tests/test_memory.py`.
  - **Depends:** P05-T02.01.
  - **Change:** Regenerate compact packet separating verified/reported/hypothesis state, unresolved questions, attempts and bounded handles for next preflight.
  - **Proof:** UNIT; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); critical missing settlement survives compression, tampered prose/principal cannot override authenticated typed state.

<a id="p05-t02-03"></a>

- [x] **P05-T02.03 — Cache exact passages by source and authorization context**
  - **Files:** `palladion/src/evidence_agent/memory/hotcache.py`, `palladion/src/evidence_agent/agent/services.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_memory.py`, `palladion/tests/test_security.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P05-T02.02.
  - **Change:** Add bounded ephemeral passage cache keyed by content/scope/generation/time; correction/close/revocation invalidates handles before readers reuse them. ADR-0041 requires separate tests for every trigger, current ACL/time and omission-safe cache behavior.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); authorized repeat hits cache, role/source change invalidates, another user never receives cached passage.

#### P05-T03 execution tasks

<a id="p05-t03-01"></a>

- [x] **P05-T03.01 — Resume a second message with revalidated evidence**
  - **Files:** `palladion/src/evidence_agent/agent/preflight.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/tests/test_end_to_end.py`, `palladion/tests/test_memory.py`.
  - **Depends:** P05-T02.03.
  - **Change:** Wire full memory/packet/cache into continuation; current material claims reread source/live facts rather than reusing old authority.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); actual explicitly enabled Groq restart/follow-up plus deterministic controls read attempts; correction/revocation/changed settlement updates answer; no hidden-thought resumption assumed.

<a id="p05-t03-02"></a>

- [x] **P05-T03.02 — Measure long-session recall and packet omissions**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** P05-T03.01.
  - **Change:** Compare fixed B4/B5 continuations with varying compression per ADR-0041; score actual persisted model/API outputs for completion, critical packet omissions, stale claims and token/call cost. Record every failed condition; no research success claim.
  - **Proof:** MEASUREMENT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); scorer catches deliberately missing critical fact; vector memory remains a separately declared treatment, not hidden B5 work.

### Atomic tasks — P06

#### P06-T01 execution tasks

<a id="p06-t01-01"></a>

- [x] **P06-T01.01 — Validate independent-context critic review output**
  - **Files:** `palladion/src/evidence_agent/agent/critic.py`, `palladion/src/evidence_agent/core/models.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_contracts.py`, `palladion/tests/test_critic.py`.
  - **Depends:** P05-T03.02.
  - **Change:** Build question/state/requirements/evidence/draft context and validate structured findings against current claim/evidence objects for finalization reader.
  - **Proof:** UNIT; [G-CRITIC](TESTING_GATES.md#g-critic-task-coverage); grounded challenge stays advisory; invented source/claim and unsupported veto cannot fabricate authoritative conflict.

<a id="p06-t01-02"></a>

- [x] **P06-T01.02 — Bound critic calls and authorized counter-search**
  - **Files:** `palladion/src/evidence_agent/agent/critic.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/agent/llm.py`, `palladion/scripts/serve.py`, `palladion/scripts/evaluate.py`, `palladion/scripts/validate_agent.py`, `palladion/tests/test_llm_transport.py`, `palladion/tests/test_critic.py`, `palladion/tests/test_agent_budget.py`.
  - **Depends:** P06-T01.01.
  - **Change:** Normally review once; cap total critic calls at three/counter-searches at two under shared tool/time budgets; revalidate new ledger evidence. Owner-approved opt-in pacing defaults0, shares the model boundary and remains inside the existing deadline; caller authority rechecks after any wait.
  - **Proof:** INTEGRATION; [G-CRITIC](TESTING_GATES.md#g-critic-task-coverage), [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); valid exception enters ledger, fourth review/third search/cross-scope target denied with counted failure.

#### P06-T02 execution tasks

<a id="p06-t02-01"></a>

- [x] **P06-T02.01 — Enforce mandatory review and critic outage policy**
  - **Files:** `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/gate.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/tests/test_critic.py`, `palladion/tests/test_gate.py`.
  - **Depends:** P06-T01.02.
  - **Change:** Replace early unavailable boundary with real critic consumer; operational/normative drafts require review and deterministic gate after finalization.
  - **Proof:** INTEGRATION; [G-CRITIC](TESTING_GATES.md#g-critic-task-coverage), [G-GATE](TESTING_GATES.md#g-gate-task-coverage); PASS cannot bypass missing slot, timeout/malformed review yields safe partial/unavailable, no unchecked directive.

<a id="p06-t02-02"></a>

- [x] **P06-T02.02 — Revalidate revisions after critic evidence changes**
  - **Files:** `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/draft.py`, `palladion/scripts/validate_agent.py`, `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_runtime_api.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P06-T02.01.
  - **Change:** Incorporate supported review in reserved final call, revalidate affected claims when counter-search changes evidence, persist review/outcome for timeline.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-CRITIC](TESTING_GATES.md#g-critic-task-coverage); explicit enabled approved-model Groq authenticated message → independent critic → scoped counter-search → reserved final → deterministic gate; T10 correction visible through answer/citation/timeline API readback; T11 fabricated objection cannot erase valid evidence or escape budget. Failures retained, no mock integration substitute.

#### P06-T03 execution tasks

<a id="p06-t03-01"></a>

- [x] **P06-T03.01 — Pair critic on/off using saved draft and ledger**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`, `palladion/tests/test_critic.py`.
  - **Depends:** P06-T02.02.
  - **Change:** Create versioned controlled critic fixtures and freeze actual canonical draft+initial ledger bindings once per case, hash/read back equal inputs across off/fixed-context/counter-search/blind-requirements conditions; actual output scorer separates changed retrieval, mechanical corrections/false objections from unadjudicated semantic outcomes (owner-approved ADR0046).
  - **Proof:** MEASUREMENT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); initial inputs hashed equal, mechanical corrections/false objections/retention loss/changed evidence/misses reported; semantic/causal veto unknown under ADR0046/0050; withheld-appendix blind spot retained.

<a id="p06-t03-02"></a>

- [x] **P06-T03.02 — Report critic cost, failures and retention conclusion**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/PROJECT_LEARNING.md`.
  - **Depends:** P06-T03.01.
  - **Change:** Report extra calls/searches/tokens/latency and correction tradeoffs beside full-runtime results; do not silently change mandatory normative-review default.
  - **Proof:** MEASUREMENT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); failed reviews retained and no best-of-N selection; neutral result cannot be relabeled accuracy gain.

### Atomic tasks — P07

#### P07-T01 execution tasks

<a id="p07-t01-01"></a>

- [x] **P07-T01.01 — Create Neo4j uniqueness and provenance adapter**
  - **Files:** `palladion/src/evidence_agent/storage/neo4j.py`, `palladion/scripts/neo4j_server.py`, `palladion/pyproject.toml`, `palladion/uv.lock`, `palladion/compose.yaml`, `palladion/tests/test_graph_identity.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P06-T03.02.
  - **Change:** Pin compatible Neo4j after dependency direction; add real namespace uniqueness constraints and bounded typed upsert/read templates for graph domain.
  - **Proof:** INTEGRATION; [G-GRAPH](TESTING_GATES.md#g-graph-task-coverage); concurrent verified key produces one node, unknown relation/raw model Cypher rejected; graph-off needs no running Neo4j.

<a id="p07-t01-02"></a>

- [x] **P07-T01.02 — Separate verified identity, provisional links and reviewed merges**
  - **Files:** `palladion/src/evidence_agent/graph/identity.py`, `palladion/src/evidence_agent/graph/registry.py`, `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/graph_schema.sql`, `palladion/tests/test_storage.py`, `palladion/tests/test_graph_identity.py`.
  - **Depends:** P07-T01.01.
  - **Change:** Derive verified namespace keys or source-scoped provisional IDs; require authorized equivalence attestation and preserve reconstructible before/after merge refs.
  - **Proof:** INTEGRATION; [G-GRAPH](TESTING_GATES.md#g-graph-task-coverage); T05/T06 safe under races; same name/category cannot merge, rejected and approved merge history retained.

<a id="p07-t01-03"></a>

- [x] **P07-T01.03 — Extract typed source-linked relation candidates**
  - **Files:** `palladion/src/evidence_agent/graph/relations.py`, `palladion/src/evidence_agent/ingest/graph_extract.py`, `palladion/tests/test_graph_identity.py`.
  - **Depends:** P07-T01.02.
  - **Change:** Validate relation allowlist, review/provenance states and exact spans; extraction feeds graph without promoting inferred edges to authority.
  - **Proof:** UNIT; [G-GRAPH](TESTING_GATES.md#g-graph-task-coverage); explicit/unreviewed labels retained; unsupported relation/missing source/rejected edge cannot authorize material claim.

#### P07-T02 execution tasks

<a id="p07-t02-01"></a>

- [x] **P07-T02.01 — Traverse bounded paths back to canonical passages**
  - **Files:** `palladion/src/evidence_agent/retrieval/graph_expand.py`, `palladion/tests/test_graph_identity.py`, `palladion/tests/test_security.py`.
  - **Depends:** P07-T01.03.
  - **Change:** Traverse authorized anchors under hop/edge/node/time caps; resolve neighbors to source passages with current ACL/time before evidence assembly.
  - **Proof:** INTEGRATION; [G-GRAPH](TESTING_GATES.md#g-graph-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); known exception recovered, restricted inferred neighbor never exposed, high-degree hub obeys bounds.

<a id="p07-t02-02"></a>

- [x] **P07-T02.02 — Wire optional graph into retrieval and publication**
  - **Files:** `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/ingest/pipeline.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/settings.py`, `palladion/src/evidence_agent/main.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/agent/services.py`, `palladion/src/evidence_agent/agent/search_worker.py`, `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/scripts/serve.py`, `palladion/scripts/seed.py`, `palladion/scripts/reconcile.py`, `palladion/tests/test_end_to_end.py`, `palladion/config/settings.yaml`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P07-T02.01.
  - **Change:** Enable graph only as declared treatment; required-backend set/status markers reflect graph on/off; optional outage falls back explicitly through hybrid reader.
  - **Proof:** INTEGRATION; [G-GRAPH](TESTING_GATES.md#g-graph-task-coverage), [G-SOURCE](TESTING_GATES.md#g-source-task-coverage); graph-off reconciles, required-relation failure unavailable, graph hit cannot bypass canonical resolver.

#### P07-T03 execution tasks

<a id="p07-t03-01"></a>

- [x] **P07-T03.01 — Measure graph's incremental evidence against B2**
  - **Files:** `palladion/scripts/evaluate_graph.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_end_to_end.py`, `palladion/tests/test_graph_identity.py`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P07-T02.02.
  - **Change:** Run paired frozen B2/B3 queries; record exception recall, identity/review effort, latency/cost and retained/disabled decision for later treatment reader.
  - **Proof:** MEASUREMENT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); selected missed appendix recovered and aggregate negatives retained; no benefit permits disable decision, never fabricated win.
  - **Evidence:** E-P07-002 uses the expressly permitted negative-result exit:0incremental appendix recoveries in4frozen pairs, both expected appendices already found byB2. Graph remains disabled. Controlled two-hop anchor recovery is integration evidence, not an empirical retrieval win. Failed/degraded runs remain preserved.

#### P07-T04 execution tasks — owner-added memory promotion

<a id="p07-t04-01"></a>

- [x] **P07-T04.01 — Persist sessions and promotion provenance with additive v6**
  - **Files:** `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/promotion_schema.sql`, `palladion/src/evidence_agent/memory/sessions.py`, `palladion/tests/test_memory_promotion.py`.
  - **Depends:** P07-T01.02.
  - **Change:** Backend-owned session lifecycle and explicit original event/chunk-offset promotion links; preserve v5 graph and older memory data, current scope/provenance and append-only decisions.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage); fresh schema, populated v5 upgrade/verified backup, failed-transaction rollback, default-client compatibility, unauthorized/closed-session rejection.

<a id="p07-t04-02"></a>

- [x] **P07-T04.02 — Classify bounded event chunks using primary deterministic PathA**
  - **Files:** `palladion/src/evidence_agent/memory/promotion.py`, `palladion/src/evidence_agent/memory/classification.py`, `palladion/tests/test_memory_promotion.py`.
  - **Depends:** P07-T04.01.
  - **Change:** Chunk approved event fields with exact offsets, classify explicit personal preferences as USER semantic, actual tool/workflow experience as unapproved procedural, and all remaining/uncertain material as session episodic. Hard source/scope checks override classification; never promote a case fact globally by repetition.
  - **Proof:** UNIT; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); positive preferences/tool experience and negative case facts, quoted/injected instructions, other-user statements, duplicate/replayed events and oversized inputs.

<a id="p07-t04-03"></a>

- [x] **P07-T04.03 — Add bounded cosine/loss PathB without overriding deterministic rules**
  - **Files:** `palladion/src/evidence_agent/memory/promotion.py`, `palladion/src/evidence_agent/memory/classification.py`, `palladion/src/evidence_agent/memory/promotion_worker.py`, `palladion/src/evidence_agent/retrieval/embeddings.py`, `palladion/scripts/promote_memory.py`, `palladion/tests/test_memory_promotion.py`.
  - **Depends:** P07-T04.02.
  - **Change:** Use existing pinned local encoder and frozen labeled category examples for optional fallback/additional scoring; deterministic-dominant weighting, cosine margin loss, explicit bounds and abstention. Record model/config/scores/loss; no new Groq classifier or training/calibration claim.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); actual encoder comparison plus deterministic controls showing hard rejection cannot be reversed, uncertain margins remain episodic and work is bounded.

<a id="p07-t04-04"></a>

- [x] **P07-T04.04 — Wire automatic writes and session-scoped recall through runtime readers**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/memory/packet.py`, `palladion/src/evidence_agent/agent/services.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/scripts/memory.py`, `palladion/tests/test_memory_promotion.py`, `palladion/tests/test_runtime_api.py`.
  - **Depends:** P07-T04.03.
  - **Change:** Promote after persisted backend events, no LLM write tool; wire explicit session/default lifecycle and session isolation into event/continuity/episodic readers. Semantic preferences cross sessions for same USER with original source ACL intact; procedural experience stays authorityNONE. Preserve operator correction/revocation and canonical case evidence readers.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-SECURITY](TESTING_GATES.md#g-security-task-coverage); real API write→close/reopen→same-user recall, session/user/case negative controls, correction/revocation and no procedural policy/execution privilege.

<a id="p07-t04-05"></a>

- [x] **P07-T04.05 — Measure and prove automatic promotion through actual consumers**
  - **Files:** `palladion/scripts/promote_memory.py`, `palladion/scripts/evaluate_graph.py`, `palladion/data/demo/memory_promotion_pilot.json`, `palladion/scripts/validate_agent.py`, `palladion/tests/test_memory_promotion.py`, `palladion/tests/test_end_to_end.py`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/RESEARCH_PROTOCOL.md`, `palladion/docs/development/PROJECT_LEARNING.md`.
  - **Depends:** P07-T04.04, P07-T03.01.
  - **Change:** Record fixed synthetic PathA/B pilot outputs, classification/abstention/cost and real next-message memory consumption; retain failures and limits. Same sole end reviewer covers full graph+memory phase and blueprint amendment.
  - **Proof:** MEASUREMENT; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); actual Groq consumes automatically stored preference/context without authority escalation; session isolation survives persisted reopen; no generalized accuracy claim without P08 labels.

### Atomic tasks — P08

#### P08-T01 execution tasks

<a id="p08-t01-01"></a>

- [x] **P08-T01.01 — Apply approved labels and freeze empirical research choices**
  - **Files:** `palladion/data/demo/goldens.jsonl`, `palladion/data/demo/p08_study.json`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`, `palladion/docs/development/RESEARCH_PROTOCOL.md`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** P07-T03.01, P07-T04.05.
  - **Change:** Apply accepted ADR-0019/Q08 and ADR-0071: persist distinct actual B0/B1 development calibration artifacts before freezing the owner-approved protocol/targets and executing family-disjoint evaluation pilots; inspected legacy T01–T24 remain regression/development. evidence two annotators/adjudication or label pilot-only, record disjoint splits, repetitions/uncertainty and B0/B1-calibrated targets before held-out. No new owner vote on the already accepted method or invented numerical outcome.
  - **Proof:** DOC; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); owner-approved manifest predates final run, absent independent labels stay pilot-only, near-duplicate split leakage detected.

<a id="p08-t01-02"></a>

- [x] **P08-T01.02 — Persist reproducible manifests and scorer inputs**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`.
  - **Depends:** P08-T01.01.
  - **Change:** Capture revision/dirty hash, corpus/gold/split hashes, models/prompts/pins/config/generations, scope/randomness/cache/hardware beside actual outputs.
  - **Proof:** UNIT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); replay scorer consumes recorded output, rejects missing hashes/denominators, unavailable measurement never becomes zero.

#### P08-T02 execution tasks

<a id="p08-t02-01"></a>

- [x] **P08-T02.01 — Execute declared B0–B9 and memory-vector controls**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`.
  - **Depends:** P08-T01.02, P08-T02.03, P08-T02.04, P08-T02.05, P08-T02.06.
  - **Change:** Implement declared treatment/parent switches and repeated model/frozen retrieval controls; isolate raw ablations from operational release and account every call.
  - **Proof:** MEASUREMENT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); manifests disclose parent/capability differences and one fusion stage; no hidden critic searches, planner cost or default adaptive bypass.

<a id="p08-t02-02"></a>

- [x] **P08-T02.02 — Compute support, utility and sliced cost metrics**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_goldens.py`.
  - **Depends:** P08-T02.01.
  - **Change:** Calculate raw numerator/denominator, case-clustered uncertainty and retrieval/support/disposition/abstention/false-veto/latency/cost slices for report reader.
  - **Proof:** UNIT; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); known scorer cases cover wrong citation, safe refusal and zero denominator; refusal-only cannot appear perfect through omitted utility.

<a id="p08-t02-03"></a>

- [x] **P08-T02.03 — Implement the isolated adaptive-critic treatment**
  - **Files:** `palladion/src/evidence_agent/agent/critic.py`, `palladion/src/evidence_agent/agent/experiments.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/config/settings.yaml`, `palladion/tests/test_critic.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P08-T01.02.
  - **Change:** Use always-on labels to propose Q10 risk criteria and explicitly enable B7 in synthetic evaluation; default normative review remains mandatory.
  - **Proof:** UNIT; [G-CRITIC](TESTING_GATES.md#g-critic-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); risk false-skip fixture detected, B7 flag cannot change default release behavior; missing owner acceptance leaves treatment NOT_RUN, not a claimed result.

<a id="p08-t02-04"></a>

- [x] **P08-T02.04 — Implement the optional nonexclusive planner treatment**
  - **Files:** `palladion/src/evidence_agent/agent/preflight.py`, `palladion/src/evidence_agent/agent/experiments.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/agent/llm.py`, `palladion/config/settings.yaml`, `palladion/tests/test_agent_budget.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P08-T01.02.
  - **Change:** Add explicitly enabled B8 nonexclusive planner treatment using selected Groq model initially. Any different/smaller model needs a recorded treatment decision; preserve existing scope grants and account the extra model attempt.
  - **Proof:** UNIT; [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); disabled path has zero planner calls, failure cannot hard-route or grant scope; planner cost/attempt appears in run manifest.

<a id="p08-t02-05"></a>

- [x] **P08-T02.05 — Implement a controlled alternative fusion treatment**
  - **Files:** `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/config/settings.yaml`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_pipeline.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P08-T01.02.
  - **Change:** Select and record Q10 alternative for B9; reuse fixed candidate rankings and ensure treatment consumer performs only the declared single fusion stage.
  - **Proof:** INTEGRATION; [G-RETRIEVAL](TESTING_GATES.md#g-retrieval-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); known ranked fixtures distinguish methods, native fusion is disabled when alternative owns it; no double RRF or hidden candidate change.

<a id="p08-t02-06"></a>

- [x] **P08-T02.06 — Implement optional vector-memory augmentation**
  - **Files:** `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/memory/vector.py`, `palladion/src/evidence_agent/agent/tools.py`, `palladion/pyproject.toml`, `palladion/config/settings.yaml`, `palladion/tests/test_memory.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P08-T01.02.
  - **Change:** Owner approved ADR-0072/0073: implement pinned sqlite-vec in a separate derived sidecar, with no registry schema migration; add only needed derived memory index with scoped canonical revalidation; evaluator compares the same structured/FTS baseline.
  - **Proof:** INTEGRATION; [G-MEMORY](TESTING_GATES.md#g-memory-task-coverage), [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); disabled path unchanged, cross-case/stale vector hit rejected, index update/readback verified; no extension install or existing-data migration without authorization.

#### P08-T03 execution tasks

<a id="p08-t03-01"></a>

- [x] **P08-T03.01 — Run cross-boundary injection and revocation cases**
  - **Files:** `palladion/tests/test_security.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P08-T02.02.
  - **Change:** Run T01–T24 with source/tool/memory/graph poisoning, role/source revocation between search and release, packet tampering and privileged traces.
  - **Proof:** INTEGRATION; [G-SECURITY](TESTING_GATES.md#g-security-task-coverage), [G-E2E](TESTING_GATES.md#g-e2e-task-coverage); authorized positives work, restricted canary absent from prompt/cache/response/trace and no denied-path existence leak.

<a id="p08-t03-02"></a>

- [x] **P08-T03.02 — Inject dependency, retry, deadline and recovery failures**
  - **Files:** `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_agent_budget.py`, `palladion/tests/test_end_to_end.py`, `palladion/tests/test_live.py`, `palladion/tests/test_ingest.py`.
  - **Depends:** P08-T03.01.
  - **Change:** Exercise sparse/graph/live/model/critic outages, interrupted ingest, malformed results, parallel retries and cancellation on isolated resources.
  - **Proof:** SMOKE; [G-E2E](TESTING_GATES.md#g-e2e-task-coverage), [G-BUDGET](TESTING_GATES.md#g-budget-task-coverage); typed partial/unavailable preserves events and counts, no detached work/unbounded retry; task listeners verified stopped.

<a id="p08-t03-03"></a>

- [x] **P08-T03.03 — Reconcile trace and source artifacts through real readers**
  - **Files:** `palladion/scripts/reconcile.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/p08_integrity_controls.json`, `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/tests/test_evaluation.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P08-T03.02.
  - **Change:** Read source manifests, policy/live/gate IDs and sanitized audit through production readers; verify failure metrics/cost match actual consumed attempts.
  - **Proof:** INTEGRATION; [G-SOURCE](TESTING_GATES.md#g-source-task-coverage), [G-E2E](TESTING_GATES.md#g-e2e-task-coverage); deliberate index gap/missing correlation detected, valid trace reconstructs disposition without secrets or omitted failure cost.

#### P08-T04 execution tasks

<a id="p08-t04-01"></a>

- [x] **P08-T04.01 — Export the reproducible result set and honest conclusion**
  - **Files:** `palladion/scripts/evaluate.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/retrieval_pilot.json`, `palladion/tests/test_evaluation.py`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/PROGRESS.md`.
  - **Depends:** P08-T03.03.
  - **Change:** Export pinned manifests, scored outputs/failures and redacted summary with artifact hashes; report null/adverse findings and prototype limits.
  - **Proof:** SMOKE; [G-RESEARCH](TESTING_GATES.md#g-research-task-coverage); independent reader reconstructs metrics/cost from retained artifacts; missing/failed runs visible, no unsupported production/superiority claim.

## P09 — Post-completion audit and benchmark handoff

Parent: accepted ADR-0087–0090 and ADR-0092–0095; ADR-0091 closure rejected, PF03 remains open. Preserve blueprint locked decisions and immutable raw research. Blueprint: Locked decisions, §3/§5/§6/§7/§9/§11/§14/§16/§17/§18.

| Task | Bounded outcome | Exit |
|---|---|---|
| P09-T01 | Audit and gate correction | G-GATE, G-DOC |
| P09-T02 | Approved retrieval handoff | G-RETRIEVAL, G-SOURCE |
| P09-T03 | Provisioning and safe evaluator controls | G-SECURITY, G-RESEARCH |
| P09-T04 | Deadline, reproducibility and proof corrections | G-BUDGET, G-RESEARCH, G-E2E |
| P09-T05 | Verified consumer closeout | G-E2E, G-DOC |

Pre-adversary receipt: evidence/P09_AUDIT_AND_HANDOFF.md. P09 parent exit requires every child proven, including original PF03 performance acceptance, and independent review resolved. A verified mechanism checkpoint/T05 may close after its own dependencies, tests, review and cleanup while P09/PF03/T02.07 remain OPEN. This does not close the parent exit or waive its target.

<a id="p09-t01-01"></a>

- [x] **P09-T01.01 — Record audit and approvals**
  - **Files:** `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/evidence/P09_AUDIT_AND_HANDOFF.md`.
  - **Depends:** P08-T04.01.
  - **Change:** Record full-blueprint receipts, source-verified findings and owner contracts.
  - **Proof:** UNIT; G-E2E, G-DOC; doc checker and source verification.

<a id="p09-t01-02"></a>

- [x] **P09-T01.02 — Close mandatory-review requirement bypass**
  - **Files:** `palladion/src/evidence_agent/agent/gate.py`, `palladion/tests/test_gate.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Retain known canonical facts but qualify requirements without current review.
  - **Proof:** UNIT; G-E2E, G-DOC; complete policy absent/stale/unavailable review versus current PASS.

<a id="p09-t02-01"></a>

- [x] **P09-T02.01 — Expose document cutoff and citation readback**
  - **Files:** `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_handoff.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Optional aware document as_of preserves current source ACL/approval/revocation.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; historical/current/naive/revocation HTTP and citation controls.

<a id="p09-t02-02"></a>

- [x] **P09-T02.02 — Register approval-owned identifiers**
  - **Files:** `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/storage/exact.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_pipeline.py`, `palladion/tests/test_handoff.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Bound family/revision/identifier aliases after approval without breaking uploader consumers.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; upload approve exact lookup and unknown-code negative.

<a id="p09-t02-03"></a>

- [x] **P09-T02.03 — Batch physical coverage**
  - **Files:** `palladion/src/evidence_agent/core/retrieval.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_handoff.py`.
  - **Depends:** P09-T02.01.
  - **Change:** Bound batch readback and expose complete authorized counts/truncation without stale caching.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; more than100sources, physical drift/outage and measured backend work.

<a id="p09-t02-05"></a>

- [x] **P09-T02.05 — Remove repeated canonical coverage reads**
  - **Files:** `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/tests/test_handoff.py`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/evidence/P09_AUDIT_AND_HANDOFF.md`.
  - **Depends:** P09-T02.03.
  - **Change:** Batch canonical manifests after physical reads, preserving current principal/case/source ACL and generation checks. Measure gzip and transport without changing defaults or adding caching/dependencies.
  - **Proof:** INTEGRATION; G-SOURCE, G-RETRIEVAL; SQL count, physical drift and mid-read revocation controls; paired10/1000-source measurements. Original PF03 small-multiple target remains open if unmet; no inferred waiver.

<a id="p09-t02-04"></a>

- [x] **P09-T02.04 — Bound optional HTTP evidence budgets**
  - **Files:** `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/retrieval/embeddings.py`, `palladion/pyproject.toml`, `palladion/uv.lock`, `palladion/tests/test_retrieval.py`, `palladion/tests/test_handoff.py`.
  - **Depends:** P09-T02.01.
  - **Change:** HTTP default12/max40; tool12. Optional pinned-tokenizer whole-passage budget preserves spans.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; default/40/budget/tokenizer/span and dependency controls.

<a id="p09-t02-06"></a>

- [x] **P09-T02.06 — Implement approved explicit five-second physical audit cache**
  - **Files:** `palladion/src/evidence_agent/retrieval/audit_cache.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_handoff.py`, `palladion/docs/development/ADR_LOG.md`.
  - **Depends:** P09-T02.05.
  - **Change:** Explicit opt-in only, strict default; bounded sidecar stores healthy physical-audit keys/timestamps for at most5seconds. Recheck current canonical authorization and manifests every request, disclose cache mode/time and detection window.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-RETRIEVAL; actual HTTP/reopen hit, expiry, revocation/generation/backend separation, corruption detection window, cache failure/bounds/concurrency and paired scale/latency controls. Keep PF03 open if benefit/target unproven.

<a id="p09-t02-07"></a>

- [ ] **P09-T02.07 — Resolve original PF03 performance acceptance**
  - **Files:** `palladion/docs/development/evidence/P09_AUDIT_AND_HANDOFF.md`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** P09-T02.06.
  - **Change:** Retain fresh/cold-miss/warm-hit10/1000-source HTTP and coverage observations; resolve the original small-multiple target without waiving integrity or hiding overhead/expiry.
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-RESEARCH; disclosed mode and healthy positive controls, repeated timings, misses/failures included. Owner directed leavePF03open if cache worsens work; a mechanism or isolated warm hit does not close this acceptance.

<a id="p09-t03-01"></a>

- [x] **P09-T03.01 — Add scoped admin provisioning**
  - **Files:** `palladion/src/evidence_agent/storage/registry.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_api.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Non-admin profiles, cases and memberships; no tokens/escalation/revocation restoration.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; reopen/readback and cross-tenant/stale/non-admin/overgrant/idempotence controls.

<a id="p09-t03-02"></a>

- [x] **P09-T03.02 — Expose safe evaluator capabilities**
  - **Files:** `palladion/src/evidence_agent/agent/experiments.py`, `palladion/src/evidence_agent/evaluation/study.py`, `palladion/tests/test_evaluation.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Disclose supported isolated controls, reject unsupported serving bypasses.
  - **Proof:** UNIT; G-E2E, G-DOC; actual control consumers and default invariant regressions.

<a id="p09-t04-01"></a>

- [x] **P09-T04.01 — Enforce whole-study deadline**
  - **Files:** `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/evaluation/process_owner.py`, `palladion/scripts/evaluate.py`, `palladion/tests/test_evaluation.py`.
  - **Depends:** P09-T01.01.
  - **Change:** Cancellable local lifecycle bounds setup through scoring; retain partial attempts.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; blocked setup/final stage terminate and join with truthful accounting.

<a id="p09-t04-02"></a>

- [x] **P09-T04.02 — Bind config and correct legacy claims**
  - **Files:** `palladion/src/evidence_agent/evaluation/study.py`, `palladion/src/evidence_agent/core/evaluation.py`, `palladion/tests/test_evaluation.py`, `palladion/docs/development/evidence/P08_RESULTS.md`.
  - **Depends:** P09-T01.01.
  - **Change:** Bind consumed config bytes; preserve frozen artifacts and withdraw constant-flag semantic inference.
  - **Proof:** UNIT; G-E2E, G-DOC; tamper rejection and explicit legacy limitations.

<a id="p09-t04-03"></a>

- [x] **P09-T04.03 — Prove temporal and completeness consumers**
  - **Files:** `palladion/tests/test_gate.py`, `palladion/tests/test_end_to_end.py`, `palladion/data/demo/p08_integrity_controls.json`.
  - **Depends:** P09-T01.02.
  - **Change:** Old lexical SOP versus current policy/missing settlement at final gate; invented completeness canary rejected, scoped facts retained.
  - **Proof:** INTEGRATION; G-E2E, G-DOC; T01/T12 positive and negative controls.

<a id="p09-t05-01"></a>

- [x] **P09-T05.01 — Validate and resolve independent review**
  - **Files:** `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/PROJECT_MEMORY.md`, `palladion/docs/development/PROJECT_MAP.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `README.md`, `palladion/README.md`, `palladion/docs/README.md`, `AGENTS.md`, `palladion-benchmark/docs/development/PALLADION_FIXES.md`.
  - **Depends:** P09-T02.02, P09-T02.03, P09-T02.04, P09-T02.05, P09-T02.06, P09-T03.01, P09-T03.02, P09-T04.01, P09-T04.02, P09-T04.03.
  - **Change:** Stack checks, actual HTTP/CLI, applicable service gates, reused reviewer resolution, no-stale docs, owned-port cleanup and verified commit.
  - **Proof:** SMOKE; G-E2E, G-DOC; source/installed/gates/review/docs and scoped staged/secret proof; owner-authorized push to established main upstream.

## P10 — Owner-requested ingestion, graph setup and memory continuity extensions

Current owner GO2026-10-20; ADR0096–0098 explicitly accepted. P09/PF03 acceptance stays open, not waived by this phase. UI, enterprise adapters/writes and benchmark implementation remain excluded. Each new capability preserves the blueprint authority/ACL/four-tool invariants. The full-blueprint start adversary and sole end reviewer are complete (E-P10-001/007); current consumer gates and cleanup pass. All13P10cards are complete against published feature checkpoint c3c0950 (E-P10-008). Across the whole register125of126cards are checked; P09-T02.07 is the separate performance obligation, not a system-readiness percentage.

| Task | Outcome | Exit |
|---|---|---|
| P10-T01 | PF07 provenance-backed graph HTTP setup | G-GRAPH, G-SOURCE, G-SECURITY |
| P10-T02 | Source-preserving structured/code/PDF formats | G-SOURCE, G-CONTRACT, G-E2E |
| P10-T03 | Deterministic lexical classification and measured limits | G-MEMORY, G-RESEARCH |
| P10-T04 | Automatic bounded conversation continuity | G-MEMORY, G-SECURITY, G-BUDGET |
| P10-T05 | Clear fixture validation and public terminology | G-CONTRACT, G-DOC |
| P10-T06 | Verified checkpoint and independent review | G-E2E, G-DOC |

<a id="p10-t01-01"></a>

- [x] **P10-T01.01 — Own typed graph link provenance**
  - **Files:** `palladion/src/evidence_agent/graph/registry.py`, `palladion/src/evidence_agent/graph/relations.py`, `palladion/src/evidence_agent/ingest/graph_extract.py`, `palladion/tests/test_graph_identity.py`.
  - **Depends:** P09-T05.01.
  - **Change:** Bounded idempotent source-chunk/proof-span producer under current scoped-admin authority, preserving typed navigation and immutable proof; project only current accepted records.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t01-02"></a>

- [x] **P10-T01.02 — Expose graph link creation/readback**
  - **Files:** `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_graph_api.py`.
  - **Depends:** P10-T01.01.
  - **Change:** Upload/approve links through HTTP and reindex/reconcile actual projection; denied/unproven/stale/cross-case/revoked links cannot expose content; no fifth tool.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t02-01"></a>

- [x] **P10-T02.01 — Preserve UTF8 structured and code sources**
  - **Files:** `palladion/src/evidence_agent/ingest/parsing.py`, `palladion/src/evidence_agent/ingest/pipeline.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_pipeline.py`.
  - **Depends:** P09-T05.01.
  - **Change:** Explicit extension/MIME allowlist for JSON/JSONL/CSV/code/config; parse as source text with exact original bytes and no execution or instruction authority.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t02-02"></a>

- [x] **P10-T02.02 — Persist additive extraction provenance**
  - **Files:** `palladion/src/evidence_agent/storage/schema.sql`, `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/extraction_schema.sql`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/tests/test_storage.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_memory_promotion.py`.
  - **Depends:** P10-T02.01.
  - **Change:** v7 links original PDF digest to derived UTF8 revision/page spans/parser; existing rows preserved, new/fresh and populated upgrades/backups/rollback proven.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t02-03"></a>

- [x] **P10-T02.03 — Bound digital PDF extraction**
  - **Files:** `palladion/src/evidence_agent/ingest/extraction.py`, `palladion/src/evidence_agent/ingest/pdf_worker.py`, `palladion/src/evidence_agent/evaluation/process_owner.py`, `palladion/tests/test_extraction.py`.
  - **Depends:** P10-T02.02.
  - **Change:** Pinned parser in owned process with hard deadline/memory/input/page/output bounds; encrypted/image-only/malformed/decompression limits fail explicitly; immutable original and exact derived spans.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t02-04"></a>

- [x] **P10-T02.04 — Wire PDF upload and citation consumers**
  - **Files:** `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/main.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/tests/test_formats_api.py`.
  - **Depends:** P10-T02.03.
  - **Change:** Dedicated bounded import, current uploader/approver/source ACL and authorized original/provenance readback; source search/citation exposes PDF extraction/page lineage.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t03-01"></a>

- [x] **P10-T03.01 — Expand deterministic lexical classifier**
  - **Files:** `palladion/src/evidence_agent/memory/classification.py`, `palladion/src/evidence_agent/memory/promotion.py`, `palladion/tests/test_memory_promotion.py`, `palladion/tests/test_classification.py`.
  - **Depends:** P09-T05.01.
  - **Change:** Versioned lexical scoring, phrases/short forms, safe unapproved procedural patterns and episodic abstention; hard attribution/privacy/scope exclusions dominate; profile binds actual rules.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t03-02"></a>

- [x] **P10-T03.02 — Measure classifier tradeoffs**
  - **Files:** `palladion/src/evidence_agent/core/evaluation.py`, `palladion/data/demo/p10_classification_controls.json`, `palladion/tests/test_classification.py`.
  - **Depends:** P10-T03.01.
  - **Change:** Frozen synthetic positive/near-miss controls with per-category FP/FN/precision/recall/abstention; explain bag-of-words/cosine/Euclidean/entropy limits without training/generalization claims.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t04-01"></a>

- [x] **P10-T04.01 — Own bounded conversation context**
  - **Files:** `palladion/src/evidence_agent/core/models.py`, `palladion/src/evidence_agent/memory/store.py`, `palladion/src/evidence_agent/memory/packet.py`, `palladion/tests/test_memory.py`, `palladion/tests/test_memory_promotion.py`.
  - **Depends:** P10-T03.01.
  - **Change:** Optional typed own-actor/session turns, stable event IDs/ordering and current goal; safe released answer/claims only, revalidate citations, no reasoning/rejected draft or corrected/revoked text resurrection.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t04-02"></a>

- [x] **P10-T04.02 — Prove automatic next-turn consumption**
  - **Files:** `palladion/src/evidence_agent/agent/preflight.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/tests/test_runtime_api.py`, `palladion/tests/test_end_to_end.py`.
  - **Depends:** P10-T04.01.
  - **Change:** Persist first request/release, reopen build packet automatically, follow-up reaches actual model prompt; session/actor isolation, budget/omission and revocation negatives; actual Groq proof if generative integration changed.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t05-01"></a>

- [x] **P10-T05.01 — Simplify only evidenced fixture duplication**
  - **Files:** `palladion/src/evidence_agent/core/fixtures.py`, `palladion/tests/test_goldens.py`.
  - **Depends:** P09-T05.01.
  - **Change:** Inspect validation bodies; consolidate demonstrably repeated time-source lookup while preserving rejection/error meaning. Keep clear guards, avoid ternary/while obfuscation.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY, G-MEMORY, G-E2E; owning positive/negative controls and reopened production consumer; no skipped check reported as PASS.

<a id="p10-t05-02"></a>

- [x] **P10-T05.02 — Explain terminology and automatic versus explicit operations**
  - **Files:** `README.md`, `palladion/README.md`, `palladion/docs/README.md`, `palladion/docs/development/evidence/P10_CLASSIFICATION_AND_FORMATS.md`.
  - **Depends:** P10-T01.02, P10-T02.04, P10-T04.02, P10-T05.01.
  - **Change:** Source-grounded glossary, live mock tool flow, ingestion/memory distinction and automatic packet versus optional recall; supported formats and classifier research limits.
  - **Proof:** SMOKE; G-E2E, G-DOC; actual entrypoints and immutable source/provenance readback, review receipt, no stale claims or unverified completion.

<a id="p10-t06-01"></a>

- [x] **P10-T06.01 — Verify end to end and resolve final review**
  - **Files:** `AGENTS.md`, `palladion/docs/development/MASTER_DEV_PLAN.md`, `palladion/docs/development/GOAL.md`, `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/PROJECT_MEMORY.md`, `palladion/docs/development/PROJECT_MAP.md`, `palladion/docs/development/PROJECT_LEARNING.md`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/TESTING_GATES.md`, `palladion/docs/development/REQUIREMENTS_TRACEABILITY.md`, `palladion/docs/development/RESEARCH_PROTOCOL.md`, `palladion/docs/development/RISKS_AND_OPEN_QUESTIONS.md`, `palladion/docs/development/check_docs.py`, `palladion/pyproject.toml`, `palladion/uv.lock`, `palladion/scripts/validate_p10.py`, `palladion-benchmark/docs/development/PALLADION_FIXES.md`.
  - **Depends:** P10-T05.02, P10-T03.02.
  - **Change:** Stack/source/installed/actual service gates, one LunaMedium end reviewer/resolution, current docs/handoff completion, backup/own-port cleanup and scoped descriptive checkpoint; preserve PF03 and foreign work.
  - **Proof:** SMOKE; G-E2E, G-DOC; actual entrypoints and immutable source/provenance readback, review receipt, no stale claims or unverified completion.

## P11 — Evidence-path remediation from the benchmark's findings

Owner GO 2026-10-27 (benchmark investigation; "all of the fixes ... an actual fix not a monkey patch"); ADR-0102–ADR-0109. The benchmark found Palladion's retriever returning almost none of the governing policy evidence on version, exception and conflict questions, and about 1.9 s per search. Six read-only investigations and three independent reviews (Haiku 5.5, High) traced it to execution defects in the evidence path, not to the retrieval design: an applicability instant that could not reach an older governing version, neighbour expansion that spent the result slots, eligibility applied after a fixed top 40, an identifier lane that ranked citing tickets ahead of the defining policy and discarded every semantic result for an unknown code, chunks that carried no title, agent defaults of two passages, and publication steps that were not atomic. The blueprint's flow is unchanged; locked decisions are refined, not removed (ADR-0102 amends ADR-0101 and ADR-0087; ADR-0105 keeps the no-near-substitute rule for a bare unknown code). Subagents for this phase are read-only Haiku 5.5 High reviewers, as many as needed, under the owner's message of 2026-10-27 (replacing the Luna Medium start/end-only rule for this phase). No separate pre-phase adversary was dispatched: the six investigations that preceded the phase were the challenge of the baseline, and three independent reviewers (dead and stacked code, object-oriented design, test strength) read the first implementation group; their findings and dispositions are in E-P11-001.

| Task | Outcome | Exit |
|---|---|---|
| P11-T01 | Search returns the governing evidence: applicability instants, eligibility prefilter, bounded context, defining-first identifier lane | G-RETRIEVAL, G-SOURCE, G-SECURITY |
| P11-T02 | Chunks carry their title; banners and headings join their text; the index reads that context; populated databases upgrade and re-index | G-SOURCE, G-CONTRACT, G-RETRIEVAL |
| P11-T03 | The agent asks for enough ranked passages and sees which policy and version each comes from | G-RETRIEVAL, G-E2E |
| P11-T04 | Publication is atomic and fails closed; readers take no write lock | G-SOURCE, G-SECURITY |
| P11-T05 | Search speed: measured stage times, search-path audit, reranker | G-RETRIEVAL, G-BUDGET |
| P11-T07 | Exact codes and named versions: a code in a title defines its section, the reranker leaves the exact lane in place, a question that names a version is answered by it | G-RETRIEVAL, G-SOURCE, G-SECURITY |
| P11-T06 | End to end: stack gates, benchmark re-measurement at the new commit, final review and checkpoint | G-E2E, G-DOC |

<a id="p11-t01-01"></a>

- [x] **P11-T01.01 — Applicability value object and eligibility prefilter**
  - **Files:** `palladion/src/evidence_agent/storage/applicability.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/storage/registry.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/src/evidence_agent/core/retrieval.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/tests/search_support.py`, `palladion/tests/test_search_correctness.py`, `palladion/tests/test_search_guards.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P10-T06.
  - **Change:** One `Applicability` rule shared by the resolver, the prefilter and coverage; candidates are offered only from index generations that can apply; the resolver reads one snapshot, takes no write lock and keeps the canonical checks as the authority; exclusions are counted by reason.
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-SOURCE, G-SECURITY; positive and negative controls (near-duplicate crowding, an index that ignores the filter, restricted and foreign-case revisions, tampered original) and 19 planted mutants killed; E-P11-001.

<a id="p11-t01-02"></a>

- [x] **P11-T01.02 — Search orchestration: bounded context and the identifier lane**
  - **Files:** `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/storage/exact.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/retrieval/graph_expand.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/src/evidence_agent/telemetry/audit.py`, `palladion/tests/test_search_correctness.py`, `palladion/tests/test_search_guards.py`.
  - **Depends:** P11-T01.01.
  - **Change:** Ranked passages first with a bounded context share; defining chunks lead, widely cited codes trail, an unknown code is named without discarding semantic results and a bare unknown code returns nothing; nothing the lane did not reach is called unknown; an empty eligible set and all-excluded results are warned.
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-SECURITY; exact-lane order isolated with a frozen semantic candidate, the 5/6 mention boundary and the truncation case; E-P11-001.

<a id="p11-t01-03"></a>

- [x] **P11-T01.03 — The case's instants reach the agent, the HTTP routes and the ledger**
  - **Files:** `palladion/src/evidence_agent/agent/search_worker.py`, `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/src/evidence_agent/policy/temporal.py`, `palladion/tests/test_handoff.py`, `palladion/tests/test_search_guards.py`.
  - **Depends:** P11-T01.01.
  - **Change:** The backend derives the case's trusted instants (opening, named domain events, fresh verified transaction times) for search and for reading a citation back; the model has no argument for them; more than the bound fails visibly; one reader of the case's opening time.
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-SECURITY; the older citation reads back only with its instants; `KnowledgeArgs` forbids any time field; E-P11-001.

<a id="p11-t02-01"></a>

- [x] **P11-T02.01 — Chunk context, heading path and boundary-aware cuts**
  - **Files:** `palladion/src/evidence_agent/ingest/parsing.py`, `palladion/src/evidence_agent/ingest/chunking.py`, `palladion/src/evidence_agent/core/retrieval.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/retrieval/rerank.py`, `palladion/tests/test_chunk_context.py`.
  - **Depends:** P11-T01.01.
  - **Change:** Banners and headings join the block below them, chunks keep a heading path, the encoder, BM25 and reranker read it while citation text stays the original bytes, oversized blocks are cut at a line, sentence or space, and the representation fingerprint pins the text form.
  - **Proof:** INTEGRATION; G-SOURCE, G-RETRIEVAL; E-P11-001.

<a id="p11-t02-02"></a>

- [x] **P11-T02.02 — Schema 8 and safe re-indexing**
  - **Files:** `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/tests/test_storage.py`, `palladion/tests/test_ingest.py`, `palladion/tests/test_memory_promotion.py`, `palladion/tests/legacy_schema.py`.
  - **Depends:** P11-T02.01.
  - **Change:** `p02_chunks.heading_path_json` and `exact_aliases.defining` with a backfilling migration; a stored chunk may be relabelled once per parser version but its span, text and hashes never change; earlier generations are not served until indexed again.
  - **Proof:** INTEGRATION; G-SOURCE, G-CONTRACT; fresh creation, populated v7 upgrade with rollback, relabel and conflict controls, the unserved-until-reindexed cliff; E-P11-001.

<a id="p11-t03-01"></a>

- [x] **P11-T03.01 — Agent defaults and the model's view of a passage**
  - **Files:** `palladion/src/evidence_agent/agent/tools.py`, `palladion/src/evidence_agent/agent/critic.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/tests/test_critic.py`, `palladion/tests/test_search_correctness.py`.
  - **Depends:** P11-T01.03.
  - **Change:** Default limit 8 and reranked, defaults visible in the schema, the critic counter-search asks for 6, a bounded number of parallel search processes, and a document passage shows its family, heading path and validity window.
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-E2E; E-P11-001.

<a id="p11-t04-01"></a>

- [x] **P11-T04.01 — Atomic publication and race guards**
  - **Files:** `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/storage/exact.py`, `palladion/src/evidence_agent/storage/sqlite.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/api/routes.py`, `palladion/tests/test_search_guards.py`, `palladion/tests/test_search_correctness.py`, `palladion/tests/test_storage.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P11-T01.01.
  - **Change:** A predecessor keeps answering until its successor can be served, aliases are written all together and reported when bounded, schema steps and collection creation are safe against a second opener, readers take no write lock.
  - **Proof:** INTEGRATION; G-SOURCE, G-SECURITY; E-P11-001.

<a id="p11-t05-01"></a>

- [x] **P11-T05.01 — Measure, then speed up the search path**
  - **Files:** `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/src/evidence_agent/retrieval/rerank.py`, `palladion/src/evidence_agent/storage/qdrant.py`, `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/tests/test_handoff.py`, `palladion/tests/test_retrieval.py`.
  - **Depends:** P11-T01.02.
  - **Change:** Per-stage timing on the real runtime first; then the counted audit on the search path and the reranker settings, each as far as the measurement showed (ADR-0109, owner-approved direction). The long-lived search worker and the multilingual reranker candidate are not built and stay recorded as open in ADR-0109 and RISKS.
  - **Proof:** MEASUREMENT; G-RETRIEVAL, G-BUDGET; before and after timings on the same corpus, ranking unchanged unless disclosed.

<a id="p11-t06-01"></a>

- [ ] **P11-T06.01 — Verify end to end, re-measure in the benchmark and close**
  - **Files:** `palladion/docs/development/MASTER_DEV_PLAN.md`, `palladion/docs/development/PROGRESS.md`, `palladion/docs/development/EVIDENCE_LOG.md`, `palladion/docs/development/GOAL.md`.
  - **Depends:** P11-T07.01, P11-T05.01, P11-T04.01, P11-T03.01, P11-T02.02.
  - **Change:** Stack gates, actual entry-point smoke, the benchmark's Track A and Track B re-run for the Palladion arms at the new commit, end review and resolution, scoped commit.
  - **Proof:** SMOKE; G-E2E, G-DOC; benchmark evidence pointers and no stale claims.

<a id="p11-t07-01"></a>

- [x] **P11-T07.01 — Exact codes and named versions**
  - **Files:** `palladion/src/evidence_agent/storage/applicability.py`, `palladion/src/evidence_agent/storage/catalog.py`, `palladion/src/evidence_agent/storage/exact.py`, `palladion/src/evidence_agent/retrieval/hybrid.py`, `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/src/evidence_agent/retrieval/coverage.py`, `palladion/tests/test_exact_codes.py`, `palladion/tests/test_search_correctness.py`.
  - **Depends:** P11-T01.02.
  - **Change:** The benchmark's exact-code questions found the complete set for 3 of 10 where keyword search found 8. Causes read from the running system: a code that titles a section was only one of many mentions; the reranker moved the exact lane's chunks behind semantic hits; a full stop closing a sentence was part of the code; and a question that names a replaced version (`POL-001@v1`) can never be answered because the version is no longer eligible. A code in a chunk's title defines it, the cross-encoder orders only what the index found, a code ends on a letter or digit, and `FAMILY@vN` names the family's Nth version (ADR-0105 addendum, ADR-0110, owner-approved 2026-10-28).
  - **Proof:** INTEGRATION; G-RETRIEVAL, G-SOURCE, G-SECURITY; tests with a violating and a valid case for each rule and mutants of the new code, then the benchmark's Track A at the new commit (E-P11-003).

## Definition of done

A task is done only when acceptance, relevant gates, runnable smoke, review findings,
current documents and scoped checkpoint all have evidence. Gate skips require explicit
reason and remain unpassed. Never silently lower thresholds, delete failures, cite absent
test files as executed, or claim an experimental module exists because the plan names it.
