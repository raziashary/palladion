# Palladion benchmark master development plan

Version 1, 2026-10-18. Scope anchor: [research protocol v1.0](../vision/palladion_retrieval_benchmark_research_protocol.md), especially
§1 hypotheses, §3 fairness controls, §7 harness contracts, §13 gates, §14 execution
protocol and §22 preregistration checklist. Current mandate: the owner asked for the
development suite only (phase **B00**). Phases B01 onward are planned and need the owner's
GO; a task ID is not an approval. This benchmark does not develop the system under test:
`palladion/` belongs to another contributor and is never edited from here.

## Document authority and ownership

| Record | Authority and update trigger |
|---|---|
| Current user instruction and [AGENTS](../../AGENTS.md) | Scope and approval constraints; resolve before dependent work |
| Research protocol | Intended experiment and locked method; do not quietly rewrite. Its numbers are starting proposals until sealed in B08-T03 |
| Live source, fixtures, executed tests and measurements | Actual implemented behavior; a conflict with intent is a gap to surface |
| This plan + [GOAL](GOAL.md) | Decomposition and acceptance, subordinate to user and protocol |
| [ADR_LOG](ADR_LOG.md) | Dated material decisions; append or supersede, never erase |
| [TESTING_GATES](TESTING_GATES.md) + [RESEARCH_PROTOCOL](RESEARCH_PROTOCOL.md) | Proof contracts and the operational lock procedure; change them before measuring, never after a failure |
| Atomic checkboxes + [PROGRESS](PROGRESS.md) + [EVIDENCE_LOG](EVIDENCE_LOG.md) | Plan owns task state; PROGRESS summarizes; evidence proves closure |
| [PROJECT_MEMORY](PROJECT_MEMORY.md) + [PROJECT_MAP](PROJECT_MAP.md) | Recovery and navigation, not substitutes for source or protocol |
| [PROJECT_LEARNING](PROJECT_LEARNING.md) + [RISKS_AND_OPEN_QUESTIONS](RISKS_AND_OPEN_QUESTIONS.md) | Lessons with evidence, risks and pending owner decisions |

All working documents live in this folder. A change that makes any document stale is fixed
in the same unit or queued for the owner. The Palladion suite
([master plan](../../../palladion/docs/development/MASTER_DEV_PLAN.md)) was the format
reference only; none of its phase numbers, gates or rules are imported by name.

## Task reading and execution protocol

### Before every task

1. Read the current request and [AGENTS](../../AGENTS.md). Check `git rev-parse --show-toplevel`,
   `git status --short --branch`, `git worktree list` and the unstaged diff. The checkout is
   shared with the Palladion contributor: touch only `palladion-benchmark/` paths.
2. Read [GOAL](GOAL.md), [PROGRESS](PROGRESS.md) and [PROJECT_MEMORY](PROJECT_MEMORY.md).
3. Read this plan's parent row and the exact atomic card, the relevant [ADRs](ADR_LOG.md) and
   [risks and open questions](RISKS_AND_OPEN_QUESTIONS.md). An empty or proposed ADR answer
   grants nothing.
4. Reread the protocol sections the card names plus §3.1 (fairness controls) and §22
   (checklist). A fresh contributor reads the whole protocol once.
5. Read the [testing gates](TESTING_GATES.md) and [traceability rows](REQUIREMENTS_TRACEABILITY.md)
   for the card. Know how the proof can fail before writing code.
6. Inspect owning source, producers, consumers and tests. Verify every named artifact exists.
   Paths in cards are planned until created; absence is not an invitation to fake them. When a card
   depends on Palladion, read Palladion's live source and API, not its plan.
7. State the unit, the expected observation and the checks. Log decisions in ADR_LOG immediately.

### Delegation

Owner direction (2026-10-18): subagents only as needed, and only Haiku 5.5. The default
pattern, adapted from the owner's global rules, is one independent read-only reviewer
before a phase starts (to refute its tasks, sources and proof) and one after its gates pass
(to audit the work). Both read the complete protocol in fresh context. The coordinator
does research, implementation, tests and triage, owns integration, and closes tasks.
Reviewers get no live credentials and no git access.

### Before closure

Run stack validation (`uv run pytest`, `ruff`, `mypy`), the documentation checker, the
owning gates and a representative entry-point smoke. Record exact commands, environment,
results and limits in [EVIDENCE_LOG](EVIDENCE_LOG.md). Dispatch the end-of-phase auditor,
resolve or keep open every material finding, update progress, goal, map, memory, learning
and ADR/risk records, sweep for stale statements, stop task-owned processes and confirm
ports are free, then stage only reviewed `palladion-benchmark/` paths, scan for secrets and
commit with a Conventional Commit subject and a descriptive body. The owner authorized pushing
to `main` (ADR BADR-0004); before pushing, list `git log origin/main..HEAD` and confirm only this
work is ahead.

## Sequence and status semantics

`B00 → B01 → B02 → B03 → B04 → B05 → B06 → B07 → B08 → B09`. The order is this plan's own, informed by
protocol §19.1 (fixture and label integrity before any retriever; no expensive comparators before the dataset works).
Approximate mapping: protocol Slice 1 = B02 plus the harness work in B01; Slice 2 = B03–B05; Slice 3 = B06;
Slice 4 = B07; Slice 5 = B08; Slice 6 = B09. Deviation for owner review: the protocol builds the 12k corpus before the
locked test, whereas this plan generates the M tier in B08 after all arms exist, so pilots run on the S tier only.
Slices are logical milestones, not delivery-time promises.

Task states: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`. Gate states: `NOT_RUN`,
`PARTIAL`, `PASS`, `FAIL`, `BLOCKED`. A checkbox is not proof; unchecked means unproven.
Gates that span phases stay PARTIAL until the whole contract is exercised. Run states for arms
(`NOT_RUN`, `UNSUPPORTED`, `FEATURE_NOT_SUPPORTED`, `INVALID_RUN`, `TIMEOUT`) are results, never zero scores.

### Atomic task contract

The `Bxx-Txx` rows are work packages. Execute their children in the
[atomic execution register](#atomic-execution-register); `B02-T01.01` is a stable child of
B02-T01 and suffixes are never reused or renumbered. Each card lists exact repository-relative
**Files**, explicit **Depends**, a bounded **Change** and **Proof** (kind, gate, the observation
that could fail). Proof kinds: DOC = structural or content check; UNIT = deterministic isolated
behavior; INTEGRATION = a real local store or service boundary; SMOKE = actual entry point;
MEASUREMENT = a recorded experimental result. A deterministic test may inject data to exercise a
benchmark guard, but a provider or Palladion behavior claim needs a real call. Shared files are
touched by sequential cards only. Closure records changed paths, readback, commands, evidence ID
and limits beneath the checkbox.

Exclusions: UI, real customer or company data, editing `palladion/`, and any comparator
claim before the corresponding measurement. Zero observed failures are never reported as zero risk.

## B00 — Development suite

Goal O00. Inputs: the whole protocol, the Palladion development suite and the owner's answers. No code beyond tooling bootstrap.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B00-T01 | Read protocol; establish authority, layout and scope; record decisions | All 22 sections mapped; BADR-0001–BADR-0013 recorded, with owner answers where given and OPEN states shown for the rest |
| B00-T02 | Create the linked planning, evidence and entry-point records | Every document has a distinct owner and task-start navigation |
| B00-T03 | Checker and uv bootstrap | BG-DOC passes with negative self-tests; uv environment locks and runs dev tools |
| B00-T04 | Independent review, resolution and publication | Haiku 5.5 receipt; findings dispositioned; scoped commit and push |

Exit: the suite is usable by the next session; no benchmark gate other than BG-DOC is claimed; B01 awaits GO.

## B01 — Harness foundation (Slice 1 part)

Goal O01. Read protocol §3.1, §7, §18 and §22. Depends on B00. Owner modules: contracts, registry, manifest, tracing, runner, cli, generator, configs.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B01-T01 | Tooling, dev commands, secret-safe config | Clean-clone sync and checks pass; secret scan has a working negative control |
| B01-T02 | Typed contracts and configuration | Invalid inputs rejected; null is never zero |
| B01-T03 | Registry, run manifest, tracing and budget counters | Capability matrix explicit; manifests immutable; violations recorded |
| B01-T04 | Paired bounded runner and CLI | Failures preserved as results; no selective rerun |
| B01-T05 | Shared generator pool | Explicit per-call model record; real call per approved model |

Exit: a harness that runs a fake in-test adapter end to end with manifests and ITT records, plus a proven generator entry point. No dataset or retriever result.

## B02 — Synthetic world, S-tier corpus and gold (Slice 1)

Goal O02. Read protocol §4, §5 and §6. Depends on B01. Owner modules: fixtures, generate_data. Template rendering only (BADR-0009).

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B02-T01 | Hidden world model, versions, policies, timelines | Deterministic; four as-of bases select different versions; cycles rejected |
| B02-T02 | Document and noise rendering | Critical facts preserved; actual noise proportions reported |
| B02-T03 | Manifests, ACLs and namespace separation | Published namespace has no gold; tenant isolation |
| B02-T04 | Gold schema and stratified partitioned questions | Alternative evidence sets; family-grouped splits |
| B02-T05 | Live operational mock | Read-only; deterministic; failure modes distinguishable |
| B02-T06 | Fixture and label validation | Planted defects caught |
| B02-T07 | Generation entry point, dataset card, pilot label audit | Reproducible digest; audited sample with agreement statistic |

Exit: audited S-tier dataset card and gold validation report. No retriever is run (protocol §19.1 Slice 1).

## B03 — Evaluation core (Slice 2 part)

Goal O03. Read protocol §6.1, §8, §10.2, §10.3, §12, §13.4, §14.2 and §14.3. Depends on B02 gold schema and manifest. Owner modules: eval, analysis tables.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B03-T01 | Span normalization | Chunking differences do not change identity; no phantom citations |
| B03-T02 | Evidence-set metrics | Oracle, empty and incomplete-set controls behave |
| B03-T03 | Ranking and provenance-aware metrics | Hand-computed values; wrong-vintage counted |
| B03-T04 | Statistics | Known effect recovered; interval coverage simulated |
| B03-T05 | Latency and cost | Quantiles exact; missing stays missing |
| B03-T06 | Scorecard tables | Run states shown as states |
| B03-T07 | Score-run driver | The real runner writes a run that the scorer reads; perfect, empty and shuffled arms differ |

Exit: the scorer reads output artifacts and distinguishes perfect, empty and shuffled retrievers on S-tier gold.

## B04 — Retrieval arms R0–R3, R7a and Track A pilot (Slice 2)

Goal O04. Read protocol §2.1, §3, §7.4 and §19.1 Slice 2. Depends on B02 and B03. Cross-project dependency: Palladion's retrieval interface (OQ03).

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B04-T01 | Shared harness, pins, launcher, R0 and R1 | Exact-ID and semantic probes behave; ANN loss measured; chunks tile documents |
| B04-T02 | R2 and R3 with C1/C2 and equal token budgets | Budgets equal by counted words |
| B04-T03 | R7a Palladion adapter and isolated runtime | HTTP only; no import; unavailable is NOT_RUN; Palladion's live state untouched |
| B04-T04 | Build, Track A runner, scoring entry point and result validator | No gold in artifacts; leakage rejected; test split refused |
| B04-T05 | Pilot measurement | Counts and failures recorded; no superiority claim |

Exit: Track A pilot for R0, R1, R2, R3 and R7a with manual failure inspection. Pilot excluded from held-out claims.

## B05 — Answer-level evaluation and Track B (Slice 2)

Goal O05. Read protocol §3 Track B, §9, §10 and §14.5. Depends on B04 and B01-T05. Owner modules: answer_gold, citations, claims, policy, abstention, judge_audit, track_b, score_answers. Built with injected transports; no live provider call without the owner's authorization (BADR-0028).

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B05-T07 | Answer-gold sidecar and structured answer contract | Closed claim kinds, actions and outcomes; audit digests unchanged |
| B05-T09 | Generator fault mapping and prompt barrier | Provider faults are not arm faults; a gold-marked prompt is refused |
| B05-T01 | Citation metrics | Fabrication and uncited claims counted |
| B05-T02 | Temporal and policy scoring | Basis-specific, not recency |
| B05-T03 | Abstention and loss | Always-abstain penalized |
| B05-T04 | Rubric, annotation guide and judge audit | Human or deterministic label cannot be overwritten |
| B05-T05 | Track B runner | Same generator family and budget; pairing rule enforced |
| B05-T08 | Track B scoring and validator | Planted defects rejected; clean run scored |
| B05-T06 | Track B pilot | Needs the owner's live authorization; failures preserved |

Exit: controlled retrieval-to-answer pilot with a recorded generator pool. No confirmatory claim.

## B06 — Graph and research comparators R4–R7b (Slice 3)

Goal O06. Read protocol §2.1, §3.1 items 8–9, §11.2, §21 and the pre-phase adversary E-B06-001. Depends on B04. Cross-project dependency: Palladion graph links over HTTP (R7b, PF07). Quota constraint OQ06 and approvals OQ14.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B06-T00 | Contracts, worker with counting proxy, pins | Additive only; no spend escapes the cap |
| B06-T01 | HippoRAG 2 adapter | Official path, pinned, deviations recorded |
| B06-T02 | GraphRAG Local adapter | Global is not built or merged |
| B06-T03 | LightRAG adapter | Upstream identity verified |
| B06-T04 | R7b status | Absent feature is FEATURE_NOT_SUPPORTED |
| B06-T05 | Graph metrics | Undefined metrics stay undefined |
| B06-T06 | Cold-state run on a matched subset | Indexing and query cost both reported |

Exit: Track A on a matched S subset for R4 to R6 with full costs, R7b recorded as unsupported with its reason, or recorded NOT_RUN reasons.

## B07 — System arms, memory, critic and mutations (Slice 4)

Goal O07. Read protocol §2.2, §5.3–5.4, §11, §16 and §17. Depends on B02, B04, B05 and B06. The owner has allowed changes to Palladion where a card needs them (BADR-0038); E3 and E4 are defined by BADR-0039.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B07-T00 | Palladion changes and pins: model transport, evaluator mode, evaluation clock, one pin, framework pins | Default serving unchanged; counted and capped calls; one pin |
| B07-T01 | E0 LangChain two-step | Pinned; budgeted |
| B07-T02 | E1 LangGraph loop | Matched budget |
| B07-T03 | E2 Google ADK, conditional | Without access: NOT_RUN |
| B07-T04 | E3/E4 Palladion system adapter | Usage from the proxy's book; E3 never relabelled E4 |
| B07-T05 | Episodes, update events, memory and update-consistency metrics | Episode partitions; poisoning counted; stale-index windows measured at the reader |
| B07-T06 | Critic and tool-use metrics | Injected-error pairs scored; NOT_OBSERVABLE is not zero |
| B07-T07 | Mutation and metamorphic specifications and their application | 19 mutations and 7 invariants with gold; unappliable ones recorded |
| B07-T08 | Track C runner | No cross-episode leakage |
| B07-T09 | Track C pilot | Budgets and failures recorded |

Exit: native end-to-end pilot with mutation cases, within the free tier. No confirmatory claim.

## B08 — Scale, tuning, preregistration and confirmatory run (Slice 5)

Goal O08. Read protocol §13, §14, §15, §19 and §22. Depends on B04–B07 exits. This phase seals the test set.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B08-T01 | M-tier generation and gated paraphrase | Actual composition reported; negation drop rejected |
| B08-T02 | Dev tuning, power simulation and targeted security suite | No locked-test reads; suite sized from the recorded bound |
| B08-T03 | Preregistration and seal | Hashes verify; edits flagged |
| B08-T04 | Confirmatory run | Intention-to-treat; no selective rerun |
| B08-T05 | Ablations A01–A16 | One component removed against a stated base |
| B08-T06 | Plots and reports | No single composite winner |
| B08-T07 | Final audit and publication package | Claims bounded to measured strata |
| B08-T08 | Descriptive comparison of Palladion with the other systems (BADR-0043, BADR-0044) | Matched lists, cost axis, exploratory label |

Exit: sealed, reproducible results with confidence intervals and failures. A null or adverse result is a completed experiment (protocol §19.4).

**Re-plan, 2026-10-22 (BADR-0043).** The owner wants a comparison of Palladion with the other systems now, under the free tier. B08-T01 to T05 are not run on this path (no M tier, no tuning, no seal, no confirmatory run, no ablations); they stay open and keep their dependencies. Cards B08-T08.01 to T08.06 produce a descriptive, exploratory comparison on the S tier in the order that spends nothing first, with the cost constraints applied; B08-T06.01 and B08-T07.01 report from their results. Nothing in the comparison is a confirmatory or ranking claim.

## B09 — Replication and stress (Slice 6), conditional

Goal O09. Read protocol §4.2, §14.1 Stage 3 and §5.5. Depends on B08. Deferred until the owner authorizes budget; replication only, no tuning.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B09-T01 | L-tier stress | Decoys add no correct answers |
| B09-T02 | Robustness replication | No tuning on replication |
| B09-T03 | External validation datasets | Unavailable data recorded NOT_RUN |

Exit: replication results labeled as replication; capacity limits disclosed.

## Atomic execution register

Every path is repository-relative. Paths are planned until their card closes; this suite
creates only the documents and the uv bootstrap. Execute dependencies, not file-count
order. Shared-file tasks are sequential. Each proof names an observation that could fail.

### Atomic tasks — B00

<a id="b00-t01-01"></a>

- [x] **B00-T01.01 — Read the protocol and the Palladion suite; map authority and scope**
  - **Files:** `palladion-benchmark/docs/development/REQUIREMENTS_TRACEABILITY.md`, `palladion-benchmark/docs/development/PROJECT_MEMORY.md`.
  - **Depends:** None (user request 2026-10-18).
  - **Change:** Read all 22 protocol sections and the Palladion development suite; map every section, hypothesis, ablation, mutation and planned file to an owner.
  - **Proof:** DOC; BG-DOC; all 22 sections, H1-H8, A01-A16, M01-M19 and 70 planned files have a task and a gate.
  - **Evidence:** E-B00-001 (protocol read in full; tree parsed to 70 files).

<a id="b00-t01-02"></a>

- [x] **B00-T01.02 — Record layout, delegation, generator and version-control decisions**
  - **Files:** `palladion-benchmark/docs/development/ADR_LOG.md`, `palladion-benchmark/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** B00-T01.01.
  - **Change:** Record the owner's answers (in-repo uv project, Groq three-model pool, template-first corpus, Haiku 5.5 subagents, push to main) and the coordinator decisions as editable ADRs; queue unresolved choices as open questions.
  - **Proof:** DOC; BG-DOC; every ADR has all nine fields and every accepted ADR has an owner answer.
  - **Evidence:** E-B00-001; ADR_LOG BADR-0001 to BADR-0013 (owner-answered, coordinator and OPEN states recorded).

<a id="b00-t02-01"></a>

- [x] **B00-T02.01 — Write master plan, goal, progress and testing gates**
  - **Files:** `palladion-benchmark/docs/development/MASTER_DEV_PLAN.md`, `palladion-benchmark/docs/development/GOAL.md`, `palladion-benchmark/docs/development/PROGRESS.md`, `palladion-benchmark/docs/development/TESTING_GATES.md`.
  - **Depends:** B00-T01.02.
  - **Change:** Decompose the protocol into phases B00-B09 with atomic file-owning cards, checkable outcomes, falsifiable gates and the mutation/metamorphic coverage tables.
  - **Proof:** DOC; BG-DOC; atomic register has fields, acyclic dependencies and an owner for every protocol-tree file.
  - **Evidence:** E-B00-001; checker passes on the register.

<a id="b00-t02-02"></a>

- [x] **B00-T02.02 — Write research protocol, memory, map, learning, evidence log and entry-point docs**
  - **Files:** `palladion-benchmark/docs/development/RESEARCH_PROTOCOL.md`, `palladion-benchmark/docs/development/PROJECT_MEMORY.md`, `palladion-benchmark/docs/development/PROJECT_MAP.md`, `palladion-benchmark/docs/development/PROJECT_LEARNING.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/README.md`, `palladion-benchmark/docs/README.md`, `palladion-benchmark/AGENTS.md`.
  - **Depends:** B00-T02.01.
  - **Change:** Create the operational research protocol (arms, tracks, lock procedure), one working memory, the map, learning register, evidence log, READMEs and benchmark-specific agent instructions.
  - **Proof:** DOC; BG-DOC; local links, anchors and stable IDs resolve; exactly one PROJECT_MEMORY.md.
  - **Evidence:** E-B00-001; checker passes.

<a id="b00-t03-01"></a>

- [x] **B00-T03.01 — Write the documentation checker with negative self-tests**
  - **Files:** `palladion-benchmark/docs/development/check_docs.py`.
  - **Depends:** B00-T02.02.
  - **Change:** Standard-library checker for structure, links, stable IDs, ADR fields, atomic register and protocol-tree ownership; --self-test rejects planted defects in memory.
  - **Proof:** DOC; BG-DOC; valid suite passes; each planted defect (broken link, missing field, cycle, unowned file) is rejected.
  - **Evidence:** E-B00-001; checker plus negative self-tests.

<a id="b00-t03-02"></a>

- [x] **B00-T03.02 — Bootstrap the uv project and staged virtual environment**
  - **Files:** `palladion-benchmark/pyproject.toml`, `palladion-benchmark/uv.lock`, `palladion-benchmark/.gitignore`.
  - **Depends:** B00-T03.01.
  - **Change:** uv init without workspace membership, dev tools only (pytest, ruff, mypy), uv venv and locked sync; ignore secrets, artifacts and environments.
  - **Proof:** SMOKE; BG-DOC; uv sync --locked and the dev tools run from the new environment; no runtime dependencies yet.
  - **Evidence:** E-B00-002; uv sync --locked and dev tools run.

<a id="b00-t04-01"></a>

- [x] **B00-T04.01 — Independent end-of-phase review of the suite against the protocol**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/RISKS_AND_OPEN_QUESTIONS.md`.
  - **Depends:** B00-T03.02.
  - **Change:** One Haiku 5.5 read-only reviewer reads the complete protocol and the suite; the coordinator verifies each load-bearing finding before acting.
  - **Proof:** DOC; BG-DOC; receipt names protocol sections covered and confirmed, refuted, partial and uncertain findings.
  - **Evidence:** E-B00-003; Haiku 5.5 reviewer receipt, 26 findings dispositioned.

<a id="b00-t04-02"></a>

- [x] **B00-T04.02 — Resolve findings, sweep for stale statements, commit and push**
  - **Files:** `palladion-benchmark/docs/development/PROGRESS.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B00-T04.01.
  - **Change:** Fix in-scope findings, rerun the checker and its self-test, review the scoped staged diff for secrets, commit only palladion-benchmark paths, push main after confirming only this work is ahead of origin.
  - **Proof:** DOC; BG-DOC; checker and self-test pass on the committed tree; git diff --cached lists only palladion-benchmark paths.
  - **Evidence:** E-B00-004; scoped commit and push.

### Atomic tasks — B01

<a id="b01-t01-01"></a>

- [x] **B01-T01.01 — Finish project tooling and secret-safe configuration**
  - **Files:** `palladion-benchmark/pyproject.toml`, `palladion-benchmark/uv.lock`, `palladion-benchmark/.gitignore`, `palladion-benchmark/.env.example`, `palladion-benchmark/Makefile`, `palladion-benchmark/docker-compose.yml`, `palladion-benchmark/benchmark/__init__.py`, `palladion-benchmark/benchmark/secret_scan.py`, `palladion-benchmark/tests/test_secret_scan.py`.
  - **Depends:** B00-T04.02, BADR-0014.
  - **Change:** Package skeleton, dev commands via uv with a Make wrapper, .env.example holding variable names only, runtime pins httpx==0.28.1 (same as Palladion) and PyYAML, an optional Qdrant-only compose file (for machines with Docker; this machine has none, so Qdrant runs Docker-free per BADR-0017) pinned to the image tag Palladion uses on its own port 127.0.0.1:17333 with every service behind a profile, and a stdlib secret scanner (specified patterns plus an opt-in exact-value scan of the local .env with a minimum match length, never printing matches; test fixtures build fake keys at runtime). make is not installed and Docker cannot run on this machine, so the Makefile and compose file get static checks only and their execution is recorded NOT_RUN.
  - **Proof:** SMOKE; BG-HARNESS, BG-SECURITY; clean-clone uv sync --locked, pytest, ruff and mypy pass; a planted fake key in a staged file is caught and a clean tree passes; the compose file has no service outside a profile and the Makefile recipes parse; execution of make and compose is NOT_RUN with the reason recorded.
  - **Evidence:** E-B01-002; 23+ secret-scan tests, clean-copy sync/lint/types/tests pass; make not run (not installed) and Docker cannot run here (BADR-0017).

<a id="b01-t02-01"></a>

- [x] **B01-T02.01 — Typed retrieval contracts**
  - **Files:** `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/tests/test_adapter_contracts.py`.
  - **Depends:** B01-T01.01.
  - **Change:** RetrievalRequest, EvidenceCandidate and the RetrieverAdapter protocol as frozen dataclasses whose mappings and sequences are deep-copied into read-only forms; native_citation_supported is required with no default and must be backed by a non-null source_version_id when true (BADR-0016); request filters use an allowlist of arm-visible keys and string values are screened for gold-like markers (BI01, BI03); timestamps must be timezone-aware and are normalized to UTC; free-text query content is not screened here (fixture validation in B02 owns that).
  - **Proof:** UNIT; BG-HARNESS; naive timestamps, non-positive ranks, bool or float where an int is required, NaN and infinity, unknown fields, a gold-like key and a gold-like value in a benign field are rejected; mutating the source dict after construction leaves the object unchanged; a benign request and a valid round trip pass.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; contract tests with planted-defect mutations all killed.

<a id="b01-t02-02"></a>

- [x] **B01-T02.02 — Case contracts, evidence statuses and run-status taxonomy**
  - **Files:** `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/tests/test_adapter_contracts.py`.
  - **Depends:** B01-T02.01.
  - **Change:** CaseRequest, CaseResponse, SystemAdapter, five evidence statuses, abstention reasons, run states OK, NOT_RUN, UNSUPPORTED, FEATURE_NOT_SUPPORTED, INVALID_RUN, TIMEOUT, an error origin (harness, provider or arm) and the adapter exceptions that map to run states.
  - **Proof:** UNIT; BG-HARNESS; null latency or cost is never coerced to zero; an unknown status is rejected; each adapter exception maps to exactly one run state and origin.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; failure-to-run-state mapping and null handling tested.

<a id="b01-t02-03"></a>

- [x] **B01-T02.03 — Configuration files and typed loaders**
  - **Files:** `palladion-benchmark/configs/benchmark.yaml`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/configs/evaluation.yaml`, `palladion-benchmark/configs/fixtures.yaml`, `palladion-benchmark/benchmark/config.py`, `palladion-benchmark/tests/test_config_loader.py`.
  - **Depends:** B01-T02.02.
  - **Change:** Tiers S/M/L, seeds, K values 5/10/20, 4k/8k token budgets, split sizes, generator pool settings, arm pins and metric definitions. A safe YAML loader rejects duplicate keys and unknown keys; pins are an allowlist (40-hex commit, exact version, or the explicit placeholder UNPINNED, which confirmatory mode also rejects; main, HEAD, latest and ranges are rejected; version-like pins must be quoted strings).
  - **Proof:** UNIT; BG-HARNESS; a duplicate key, an unquoted 3.10, a floating latest or branch pin in confirmatory mode and an unknown key are rejected; the same file loads identically twice.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 49 config tests, real files load, confirmatory mode refuses UNPINNED.

<a id="b01-t03-01"></a>

- [x] **B01-T03.01 — Arm registry with capability declarations**
  - **Files:** `palladion-benchmark/benchmark/registry.py`, `palladion-benchmark/benchmark/adapters/__init__.py`, `palladion-benchmark/tests/test_adapter_contracts.py`.
  - **Depends:** B01-T02.03.
  - **Change:** Register arms R0-R7b and E0-E4 with declared capabilities (native citation, ACL filter, temporal filter, graph, offline cost) as SUPPORTED, UNSUPPORTED or UNVERIFIED with a source note; UNVERIFIED blocks any run that depends on that capability; E3 and E4 are pinned to FEATURE_NOT_SUPPORTED per OQ11; render the capability matrix.
  - **Proof:** UNIT; BG-ADAPTER; an arm with a missing declaration is rejected; unsupported and unverified capabilities print as words, never blank; a run depending on an UNVERIFIED capability is refused; E3 cannot be declared available.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 15 arms registered, matrix prints words, UNVERIFIED blocks runs.

<a id="b01-t03-02"></a>

- [x] **B01-T03.02 — Immutable run manifest and reproducibility checklist**
  - **Files:** `palladion-benchmark/benchmark/run_manifest.py`, `palladion-benchmark/tests/test_run_manifest.py`, `palladion-benchmark/docs/reproducibility.md`.
  - **Depends:** B01-T02.03.
  - **Change:** Manifest implementing the full protocol 7.2 schema (run id, track, arm, split, source, question and evaluator-only gold digests, benchmark commit, system-under-test commit with source-tree digest and dirty-file list from read-only git calls, method version, image digest, model versions, retrieval config, prompt digest, hardware, pricing snapshot, seed, cache condition, start time) with a stated reason wherever a value is null; self-digest in canonical JSON, exclusive-create write before the first arm runs, digest recorded externally in every ledger record; confirmatory mode refuses a dirty tree and the benchmark and the system under test are checked separately; start the reproducibility checklist.
  - **Proof:** UNIT; BG-REPRO; one changed byte changes the digest; an edit with a recomputed in-file digest is caught by the externally recorded digest; a second write to the same path is refused; gold digest never appears in the arm-visible view; a dirty or unpinned tree is refused in confirmatory mode.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 45 manifest tests incl. external-digest tamper check and read-only git capture.

<a id="b01-t03-03"></a>

- [x] **B01-T03.03 — Stage-span tracing and call-budget instrumentation**
  - **Files:** `palladion-benchmark/benchmark/tracing.py`, `palladion-benchmark/tests/test_budget_enforcement.py`.
  - **Depends:** B01-T02.02.
  - **Change:** Spans for the protocol stage list with wall time, tokens, retries, errors and cache hits; counters for main <=5 and critic <=3 with two semantics: calls the harness controls are refused before dispatch, and counts self-reported by a system under test are recorded as unverified and flagged as failures when over budget.
  - **Proof:** UNIT; BG-HARNESS; a sixth main call is flagged as a failure rather than truncated; an over-budget self-report is recorded UNVERIFIED and flagged; absent usage stays null.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 21 tracing and budget tests; concurrency test, race-freedom not proven.

<a id="b01-t04-01"></a>

- [x] **B01-T04.01 — Paired, bounded, randomized runner**
  - **Files:** `palladion-benchmark/benchmark/runner.py`, `palladion-benchmark/tests/test_runner.py`.
  - **Depends:** B01-T03.01, B01-T03.02, B01-T03.03.
  - **Change:** Same-case pairing across arms, per-case arm order randomized by a sha256-derived seeded RNG whose seed is in the manifest, per-case reset, per-case deadlines, run-level limits applied between cases only (a whole case is NOT_RUN for every arm), intention-to-treat records, a predeclared transient-retry rule fixed in the manifest, an append-only ledger keyed by run, arm, question and attempt with one final outcome per pair, a plan-digest registry that refuses a second run of the same plan unless declared a resume, and an arm that timed out is marked unusable with late results discarded and counted.
  - **Proof:** INTEGRATION; BG-HARNESS; a crashing arm is recorded INVALID_RUN and never dropped; a transient error once yields two readable attempt records and one final outcome; a selective rerun, within a run or by a new run id on the same plan, is refused; a stub that sleeps past its deadline then writes leaves a single TIMEOUT outcome and no later write.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 26 runner tests; every planted runner defect killed.

<a id="b01-t04-02"></a>

- [x] **B01-T04.02 — Top-level command line**
  - **Files:** `palladion-benchmark/benchmark/cli.py`, `palladion-benchmark/tests/test_cli.py`.
  - **Depends:** B01-T04.01.
  - **Change:** Commands for config validation, arm listing, capability matrix and version over the existing modules.
  - **Proof:** SMOKE; BG-HARNESS; capability-matrix exits 0 with all arms; an unknown arm exits nonzero.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; real entry point exits 0 and 2 as specified.

<a id="b01-t05-01"></a>

- [x] **B01-T05.01 — Shared generator pool with explicit, recorded model selection**
  - **Files:** `palladion-benchmark/benchmark/generator.py`, `palladion-benchmark/tests/test_generator_pool.py`.
  - **Depends:** B01-T02.03, B01-T03.02, B01-T03.03, BADR-0007, BADR-0008, BADR-0015.
  - **Change:** One client for the approved Groq models; each question's model is assigned before any arm runs from configured per-model token budgets (null budgets mean primary only); at call time a rate limit waits up to a capped time then fails as recorded, with no automatic switch; assign_models returns the questions that no budget covers as unassigned, and the Track B runner (B05-T05.01) records those NOT_RUN for every arm; every call records requested and served model, attempt, all request parameters (temperature, completion cap, reasoning effort, response format, timestamp), tokens, bounded rate-limit headers, request id and the statement that no provider-exposed revision exists; transport sets trust_env false and no redirects; error paths map to fixed codes; explicit enable flag and call budget enforced before dispatch.
  - **Proof:** UNIT; BG-HARNESS, BG-SECURITY; injected transport proves a hidden fallback cannot occur, every call records its model, and a planted fake key forced through each error path appears in no output, record or manifest; this does not establish provider behavior.
  - **Evidence:** E-B01-003, E-B01-005, E-B01-006; 69 generator tests; planted key through every error path appears nowhere.

<a id="b01-t05-02"></a>

- [x] **B01-T05.02 — Real-provider proof for the generator entry point**
  - **Files:** `palladion-benchmark/benchmark/generator.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B01-T05.01, B01-T01.01, OQ01, BADR-0015.
  - **Change:** A module entry point performs one bounded real call per approved model with an explicit enable flag, a call budget of three plus classified retries and a small completion cap; record model ids, quotas observed and failures.
  - **Proof:** SMOKE; BG-HARNESS; PASS only if each approved model returns at least one real response whose served model equals the requested model; a model that fails is recorded as FAIL or NOT_RUN and the gate stays PARTIAL; key never printed.
  - **Evidence:** E-B01-004, E-B01-005; 3 of 3 approved models returned a real response with matching served model and text.

### Atomic tasks — B02

<a id="b02-t01-01"></a>

- [x] **B02-T01.01 — Seeded hidden-world entities**
  - **Files:** `palladion-benchmark/benchmark/fixtures/__init__.py`, `palladion-benchmark/benchmark/fixtures/entities.py`, `palladion-benchmark/tests/test_world.py`.
  - **Depends:** B01-T02.03, BADR-0018.
  - **Change:** Fictional Meridian Switchworks organizations, tenants, roles, principals, products, merchant classes, transaction types, error codes and case types from one seed.
  - **Proof:** UNIT; BG-FIXTURE; same seed gives byte-identical output, a different seed differs, every artifact carries the fictional marker.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t01-02"></a>

- [x] **B02-T01.02 — Document versions, policies, as-of bases and typed graph gold**
  - **Files:** `palladion-benchmark/benchmark/fixtures/knowledge.py`, `palladion-benchmark/tests/test_temporal_gold.py`.
  - **Depends:** B02-T01.01.
  - **Change:** Document families and versions with SHA-256 over the structured source, approval state, ACL, valid and record time, SUPERSEDES checked by a separate validator (construction stays permissive so mutations can plant invalid chains), typed edges with supporting source, policies with the four as-of bases, precedence, required inputs and a deterministic outcome evaluator.
  - **Proof:** UNIT; BG-FIXTURE, BG-GOLD; half-open interval boundaries exact; an injected supersession cycle is rejected by the validator; the four bases select different versions on a planted case; a retroactive clause binds only evaluations made after it was recorded; evaluator boundary cases are hand-computed.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t01-03"></a>

- [x] **B02-T01.03 — Live-event timelines and case histories**
  - **Files:** `palladion-benchmark/benchmark/fixtures/operations.py`, `palladion-benchmark/benchmark/fixtures/world.py`, `palladion-benchmark/tests/test_world.py`.
  - **Depends:** B02-T01.02.
  - **Change:** Transaction, reconciliation and merchant-status events, outages, authorization grants, and case histories separating user-reported from verified facts.
  - **Proof:** UNIT; BG-FIXTURE; reported and verified facts remain distinguishable; timelines replay identically.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t02-01"></a>

- [x] **B02-T02.01 — Authoritative document rendering**
  - **Files:** `palladion-benchmark/benchmark/fixtures/documents.py`, `palladion-benchmark/benchmark/fixtures/phrasebook.py`, `palladion-benchmark/tests/test_documents.py`.
  - **Depends:** B02-T01.02.
  - **Change:** Template renderers for SOP versions, policy clauses, runbooks, API notes, manuals and FAQs; critical IDs, dates, thresholds and negations preserved; clause ids and character offsets emitted for citation gold; render hash stored; titles and file names carry no family, stratum or split token; no LLM in this phase.
  - **Proof:** UNIT; BG-FIXTURE; a flipped negation or altered threshold is detected by the equivalence check.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t02-02"></a>

- [x] **B02-T02.02 — Support artifacts, noise and planted ambiguity**
  - **Files:** `palladion-benchmark/benchmark/fixtures/documents.py`, `palladion-benchmark/benchmark/fixtures/artifacts.py`, `palladion-benchmark/tests/test_documents.py`.
  - **Depends:** B02-T02.01, B02-T01.03, BADR-0021.
  - **Change:** Incidents and postmortems, tickets, emails, memos and drafts; near-duplicates, stale text, unapproved proposals, injection documents and structural noise; planted ambiguity (aliases, same-name merchants in different tenants, exceptions in separate documents, circular-looking references, long tables, transitive prerequisites, late approvals, retroactive clauses, withdrawals); a fixed text-only header schema for condition C1; EN/ID/mixed language; proportions measured from output by methods independent of the generator tags.
  - **Proof:** UNIT; BG-FIXTURE; a draft claiming board approval never has an approved registry state; near-duplicates are measured by shingle similarity, stale and unapproved by comparing text to registry state, and a mismatch with the generator tags is reported; a planted tag/text mismatch is caught.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t03-01"></a>

- [x] **B02-T03.01 — Corpus, ACL and identity manifests with namespace separation**
  - **Files:** `palladion-benchmark/benchmark/fixtures/manifest.py`, `palladion-benchmark/tests/test_acl_isolation.py`.
  - **Depends:** B02-T02.02.
  - **Change:** corpus_manifest records with SHA-256, immutable IDs and ACL, listed in an order shuffled by an independent seed; four physically separate namespaces (generator, published corpus, dev annotations, locked test annotations); opaque snapshot ids.
  - **Proof:** INTEGRATION; BG-FIXTURE, BG-SECURITY; a recursive listing and content scan of the published namespace finds no gold field, split, family or stratum token; the metadata visibility rule hides a tenant-B document from a tenant-A principal (enforcement by a retriever is proven in B04).
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t04-01"></a>

- [x] **B02-T04.01 — Gold evidence schema**
  - **Files:** `palladion-benchmark/benchmark/fixtures/questions.py`, `palladion-benchmark/tests/test_evidence_slots.py`.
  - **Depends:** B02-T01.02, B02-T02.01, BADR-0020.
  - **Change:** Question records carrying every protocol 6.1 field, answerability with a validated mapping to the negative mechanisms, required and forbidden claims (including existence-disclosure claims for unauthorized sources), slots with explicit states and alternative sets, minimal sets, citation spans resolved from clause ids, harm severity and per-stratum track eligibility.
  - **Proof:** UNIT; BG-GOLD; a record missing a 6.1 field is rejected; an empty alternatives list is accepted only with a stated mechanism and an ANSWERABLE record with an unsatisfiable slot is rejected; an invalid label or answerability/reason pairing is rejected; a draft cannot satisfy an approved-only slot.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t04-02"></a>

- [x] **B02-T04.02 — Stratified question generation and family-grouped partitions**
  - **Files:** `palladion-benchmark/benchmark/fixtures/question_gen.py`, `palladion-benchmark/tests/test_partitions.py`.
  - **Depends:** B02-T04.01, B02-T03.01, BADR-0020, BADR-0023.
  - **Change:** Ten strata; 100 S-tier pilot questions (10 per stratum, all in the smoke partition, none test); a partition function for any tier (M tier 10/30/60 per stratum) that assigns whole scenario families to one split over the union of all strata before paraphrase, with exact per-stratum split counts and a stated rounding rule; scenario family defined as a world object (root policy family and entity cluster); question text written by LLM-free templates screened for gold, stratum and answerability vocabulary and for document ids outside the exact-id stratum; filter values derived only from principal, case and arm condition; pseudonymous question ids from a keyed hash; tier-specific sub-seeds; EN/ID/mixed language profile; answerable/unanswerable twins.
  - **Proof:** UNIT; BG-GOLD; no scenario family spans two splits or two strata' splits; a planted cross-split paraphrase and a planted cross-stratum family are rejected; per-stratum counts and language shares hit their targets; a query containing a version id outside the exact-id stratum is refused.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t05-01"></a>

- [x] **B02-T05.01 — Deterministic read-only live operational mock**
  - **Files:** `palladion-benchmark/benchmark/fixtures/live_api.py`, `palladion-benchmark/tests/test_live_api.py`.
  - **Depends:** B02-T01.03.
  - **Change:** Named read operations over per-case snapshots with 503, stale and unauthorized modes; per-operation freshness bounds; read timestamps derived from the case evaluation time, never the wall clock.
  - **Proof:** UNIT; BG-FIXTURE; the operation allowlist holds only reads and an unknown operation fails; the same case id returns the same state; each failure mode is distinguishable and stale differs from fresh only by the declared bound.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t06-01"></a>

- [x] **B02-T06.01 — Fixture and label integrity validation**
  - **Files:** `palladion-benchmark/benchmark/fixtures/validation.py`, `palladion-benchmark/tests/test_fixture_integrity.py`.
  - **Depends:** B02-T04.02, B02-T05.01.
  - **Change:** Referential, contradiction, merge-identity, temporal, gold-support, forbidden-gold, leakage, plausible-complexity (a lexical solvability baseline with identifiers removed, template share, sentence-length spread, thresholds fixed in an ADR before measurement), over-regularity, naive-newest and naive-highest-id baselines on the version questions, gold-support checked on rendered text by an extractor the renderer does not use, and cross-tier family disjointness.
  - **Proof:** INTEGRATION; BG-FIXTURE, BG-GOLD; every check has a planted-defect negative control that it catches and a clean fixture that passes.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t07-01"></a>

- [x] **B02-T07.01 — S-tier data generation entry point and dataset card**
  - **Files:** `palladion-benchmark/scripts/generate_data.py`, `palladion-benchmark/docs/dataset_card.md`, `palladion-benchmark/tests/test_generate_data.py`.
  - **Depends:** B02-T06.01.
  - **Change:** Generate 1,200 documents and 100 pilot questions from a seed; report actual token counts, lengths, language shares, revisions, duplicates and graph degree.
  - **Proof:** SMOKE; BG-FIXTURE, BG-REPRO; two subprocess runs under different PYTHONHASHSEED, time zone and working directory give identical manifest digests; the S-tier counts are checked against the configured composition; the card states the fixtures are not real procedures.
  - **Evidence:** E-B02-002, E-B02-003 (mutation sweeps), E-B02-004 (post-phase audit); tests and planted-defect controls in the owning files.

<a id="b02-t07-02"></a>

- [x] **B02-T07.02 — Stratified pilot label audit**
  - **Files:** `palladion-benchmark/benchmark/fixtures/audit.py`, `palladion-benchmark/tests/test_label_audit.py`, `palladion-benchmark/docs/dataset_card.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B02-T07.01, OQ08, BADR-0019, BADR-0020.
  - **Change:** Build a blinded, seeded, stratified audit packet (about 30 items); the owner labels it and also checks that the cited clauses exist in the rendered text and suffice; a blinded LLM second pass runs under the BADR-0019 call budget; record agreement with denominators (owner against LLM, not human against human), disagreements, and fix or withdraw defective cases before any measurement.
  - **Proof:** MEASUREMENT; BG-GOLD; agreement statistic with denominators and the non-independence limit stated; defects found and their disposition recorded; every post-audit gold edit logged with hashes; the packet holds no gold field.
  - **Evidence:** E-B02-006, BADR-0026; 30 of 30 labelled blind then checked against the cited clauses; 29 of 30 agree with the gold (kappa 0.94); one disagreement settled, three set-question golds withdrawn.

### Atomic tasks — B03

<a id="b03-t01-01"></a>

- [x] **B03-T01.01 — Chunk-to-span normalization**
  - **Files:** `palladion-benchmark/benchmark/eval/__init__.py`, `palladion-benchmark/benchmark/eval/normalize.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/tests/test_span_alignment.py`.
  - **Depends:** B02-T04.01, B02-T03.01, B01-T02.01, BADR-0024.
  - **Change:** Add optional source_document_id and source_sha256 to EvidenceCandidate (default none, so existing arms keep working) and a GoldRecord reader that checks the gold digest; map returned chunks to document, clause and offsets by the locator grammar and the folding and containment rules fixed in BADR-0024; report exact identity and overlap separately, with overlap credit never counted in headline metrics; label alignment-only mappings.
  - **Proof:** UNIT; BG-METRIC, BG-ADAPTER; differently chunked identical text aligns; a clause split across two chunks, a chunk spanning two clauses and a re-flowed table map correctly; a stale copy earns overlap credit and no identity credit; a candidate without provenance never receives a native citation; gold read back from disk equals the gold written.
  - **Evidence:** E-B03-002, E-B03-004; 38 alignment tests: locator grammar, identity vs text alignment, spanning chunks, live ids, hash and fabricated-locator handling, gold reader; planted defects killed.

<a id="b03-t02-01"></a>

- [x] **B03-T02.01 — Slot coverage and complete evidence sets**
  - **Files:** `palladion-benchmark/benchmark/eval/evidence_sets.py`, `palladion-benchmark/tests/test_evidence_metrics.py`.
  - **Depends:** B03-T01.01, BADR-0024.
  - **Change:** SlotCoverage@K and CompleteSet@K over the alternative minimal sets of records that have satisfiable slots; records with no satisfiable evidence (unanswerable, blocked, live-unavailable) return not-applicable, never zero or one; relevance is binary slot match (BADR-0024); the unit of evaluation, deduplication and every denominator are defined in evaluation.yaml.
  - **Proof:** UNIT; BG-METRIC; an oracle retriever scores 1, an empty one 0, and seven relevant chunks missing the exception score CompleteSet 0; a partial record and an unanswerable record each behave as defined; a duplicated candidate adds nothing.
  - **Evidence:** E-B03-002, E-B03-003; 11 tests on the real fixture: oracle 1, empty 0, not-applicable records, missing exception, duplicates, OR within a slot; planted defects killed.

<a id="b03-t03-01"></a>

- [x] **B03-T03.01 — Conventional ranking metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/retrieval.py`, `palladion-benchmark/tests/test_retrieval_metrics.py`.
  - **Depends:** B03-T01.01, BADR-0024.
  - **Change:** Precision, recall, MRR, nDCG, MAP and Success at K with binary gain over slot-matched units; short lists, zero relevant units and ideal-DCG zero are defined, not guessed.
  - **Proof:** UNIT; BG-METRIC; hand-computed values match; a shuffled ranking scores below the ideal one; a list shorter than K and a record with no relevant unit follow the written rule.
  - **Evidence:** E-B03-002, E-B03-003; hand-computed precision, MRR, nDCG, MAP, success; shuffled and repeated chunks; planted defects killed.

<a id="b03-t03-02"></a>

- [x] **B03-T03.02 — Provenance-aware retrieval metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/retrieval.py`, `palladion-benchmark/tests/test_retrieval_metrics.py`.
  - **Depends:** B03-T03.01, B03-T02.01, B02-T01.02, B02-T03.01, BADR-0024.
  - **Change:** Valid-source recall, wrong-vintage intrusion (in the family, not applicable, history not allowed), forbidden-source exposure, authority confusion, exception recall, conflicting-pair recall, locator resolution, evidence density and token efficiency (whitespace-word tokens), slot kinds come from a name-to-kind table in evaluation.yaml. Noise slope, paraphrase stability and rank sensitivity need inputs no earlier phase produces and move to B07-T07.01, B08-T01.02 and B09-T01.01. The manifest gains the recorded interval and the gold a history-allowed flag so intrusion can be decided.
  - **Proof:** UNIT; BG-METRIC, BG-SECURITY; a superseded version of the governing policy ranked first is counted as intrusion; a live citation is excluded from Track A denominators; every card metric sits in exactly one metric group.
  - **Evidence:** E-B03-002, E-B03-004; provenance metrics against the fixture manifest (exposure by identity and by partial text, ACL, authority, vintage, locator, density); entity-disambiguation error moved out (BADR-0024 amendment); planted defects killed.

<a id="b03-t04-01"></a>

- [x] **B03-T04.01 — Paired statistics**
  - **Files:** `palladion-benchmark/benchmark/eval/statistics.py`, `palladion-benchmark/tests/test_statistics.py`.
  - **Depends:** B01-T02.02.
  - **Change:** Paired cluster bootstrap with a fixed method, seed and minimum cluster count (below it the interval is labelled descriptive), exact McNemar, Holm over an explicit family argument, TOST equivalence with the margin as an input and a harm-direction flag, the exact zero-failure upper bound computed from n, Brier, log loss, ECE with disclosed bins, and Monte Carlo power simulation. Non-completed pairs enter binary endpoints as failures in the intention-to-treat table and are excluded and counted in the conditional table.
  - **Proof:** UNIT; BG-STATS; a synthetic known effect is recovered; simulated CI coverage is near nominal at the pilot and test cluster counts; clustering widens the interval against the naive one; an arm that times out on hard cases changes the intention-to-treat result and not the conditional one.
  - **Evidence:** E-B03-002, E-B03-003; 25 tests: known effect recovered, simulated coverage near nominal at 12 and 30 clusters, clustered wider than naive, exact McNemar, Holm, TOST, zero-failure bound, calibration, power; planted defects killed.

<a id="b03-t05-01"></a>

- [x] **B03-T05.01 — Latency and cost accounting**
  - **Files:** `palladion-benchmark/benchmark/eval/cost_latency.py`, `palladion-benchmark/tests/test_cost_latency.py`.
  - **Depends:** B01-T03.03, B01-T04.01.
  - **Change:** p50/p90/p95/p99 by a quantile method fixed in evaluation.yaml, computed over completed calls with timed-out calls counted and reported beside as at least the deadline; online cost from ledger durations and system-reported usage, offline cost from the index record B04 writes, and the amortization formula; marginal-update costs belong to B07-T05.01. Missing values stay missing.
  - **Proof:** UNIT; BG-METRIC; hand-computed quantiles match; null cost is never summed as zero; a TIMEOUT record is not read as an observed latency.
  - **Evidence:** E-B03-002, E-B03-004; 9 tests: hand-computed quantiles, timeout censored, missing cost never zero, amortization; planted defects killed.

<a id="b03-t06-01"></a>

- [x] **B03-T06.01 — Scorecards and pairwise effect tables**
  - **Files:** `palladion-benchmark/benchmark/analysis/__init__.py`, `palladion-benchmark/benchmark/analysis/tables.py`, `palladion-benchmark/tests/test_tables.py`.
  - **Depends:** B03-T04.01, B03-T02.01, B03-T07.01.
  - **Change:** Stratum-by-arm tables with n, mean, paired difference, interval and severe-failure counts; NOT_RUN, UNSUPPORTED, INVALID_RUN and TIMEOUT listed beside, not inside, accuracy; conditional-on-completion and end-to-end success reported separately over predeclared eligible subsets.
  - **Proof:** UNIT; BG-REPORT; a planted NOT_RUN arm appears as a status, not as a zero score.
  - **Evidence:** E-B03-002, E-B03-003; 8 tests: run states beside accuracy, ITT vs conditional, harm metrics conditional only, severe counts; planted defects killed.

<a id="b03-t07-01"></a>

- [x] **B03-T07.01 — Score-run driver and control arms**
  - **Files:** `palladion-benchmark/benchmark/eval/score_run.py`, `palladion-benchmark/tests/test_score_run.py`.
  - **Depends:** B03-T01.01, B03-T02.01, B03-T03.02, B03-T04.01, B03-T05.01, B01-T04.01, B02-T04.01.
  - **Change:** Read a run directory (ledger, immutable manifest, gold) and score it: every ledger record becomes a score or a run state, never a dropped row; a perfect, an empty and a shuffled control arm run through the real Runner with an injected registry that never enters the production registry; per-stratum controls are stated because perfect and empty coincide where no evidence exists.
  - **Proof:** INTEGRATION; BG-METRIC, BG-REPORT; the three controls separate on the strata where evidence exists and are reported as not distinguishable where it does not; a planted ledger hole or a gold digest mismatch stops the scorer.
  - **Evidence:** E-B03-002, E-B03-004; real Runner with injected control registry, 18 tests: controls separate where evidence exists and coincide where it does not (per stratum), ledger hole, gold, corpus and manifest mismatches stop the scorer.

### Atomic tasks — B04

<a id="b04-t01-03"></a>

- [x] **B04-T01.03 — Shared Track A harness: chunker, counted tokens, neutral ACL filter, budgets**
  - **Files:** `palladion-benchmark/benchmark/adapters/__init__.py`, `palladion-benchmark/benchmark/adapters/common.py`, `palladion-benchmark/benchmark/adapters/models.py`, `palladion-benchmark/tests/test_adapters_common.py`.
  - **Depends:** B03-T01.01, B02-T03.01, B01-T03.01, BADR-0025.
  - **Change:** One parser and chunker for R0 to R3 over the published namespace only (an arm receives the published directory and an index directory, never the snapshot root); chunks carry document id, clause ids and character offsets so candidates arrive with harness-attributed provenance; counted tokens are whitespace words with characters also reported; a neutral filter applies the principal's tenant and role from the published manifest identically to every arm (condition C2) and can be switched off (condition C1); a budget enforcer truncates a bundle to the stated token budget and flags the truncation.
  - **Proof:** UNIT; BG-ADAPTER, BG-FAIR, BG-SECURITY; chunks tile every document with no loss and every clause maps to a chunk; the filter removes exactly the documents the manifest denies and an arm cannot be built from a path that holds annotation namespaces; two bundles at the same budget differ by at most one chunk in counted words; an over-budget bundle is truncated and flagged.
  - **Evidence:** E-B04-002, E-B04-003; chunks tile all 1,200 documents, every clause maps to a chunk, the filter equals the manifest for every principal, budgets truncate and flag.

<a id="b04-t01-04"></a>

- [x] **B04-T01.04 — Pins, dependencies and run recording**
  - **Files:** `palladion-benchmark/pyproject.toml`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/benchmark/config.py`, `palladion-benchmark/benchmark/registry.py`, `palladion-benchmark/benchmark/eval/score_run.py`, `palladion-benchmark/tests/test_adapter_pins.py`.
  - **Depends:** B04-T01.03, B03-T07.01, BADR-0005, BADR-0025.
  - **Change:** Add fastembed, onnxruntime, qdrant-client and huggingface-hub at the versions Palladion pins; extend the pin schema with repository, revision and file digests for models and with version and digest for a binary; declare each arm's capabilities honestly in the registry; the Track A runner records K, token budget, metadata condition and fusion constant in the manifest's retrieval configuration and the scorer refuses a K that differs from it.
  - **Proof:** UNIT; BG-ADAPTER, BG-REPRO; an unpinned model is refused in confirmatory mode; the scorer rejects a run scored at another K; every capability cell for R0 to R3 and R7a is a word, never blank.
  - **Evidence:** E-B04-002; pins carry revision and file digests, the scorer refuses another K, confirmatory mode refuses an unverifiable model.

<a id="b04-t01-05"></a>

- [x] **B04-T01.05 — Docker-free Qdrant launcher**
  - **Files:** `palladion-benchmark/scripts/qdrant_server.py`, `palladion-benchmark/tests/test_qdrant_launcher.py`.
  - **Depends:** B04-T01.04, BADR-0017.
  - **Change:** A checksum-pinned official standalone Qdrant release run under WSL (Ubuntu) on 127.0.0.1:17333 with its own data directory; refuses a checksum mismatch, a busy port and any attempt to use Palladion's port or store; stops only the process it started.
  - **Proof:** INTEGRATION; BG-REPRO; the launcher starts, answers a health call, stops, and leaves port 16333 untouched; a wrong checksum, a busy port and a request for Palladion's store are each refused for that reason.
  - **Evidence:** E-B04-002; real WSL start, health, stop with Palladion's ports untouched; wrong checksum, busy port and Palladion's ports refused.

<a id="b04-t01-01"></a>

- [x] **B04-T01.01 — R0 lexical arm over the shared chunks**
  - **Files:** `palladion-benchmark/benchmark/adapters/bm25.py`, `palladion-benchmark/tests/test_bm25.py`.
  - **Depends:** B04-T01.03, B03-T01.01, B02-T03.01, B01-T03.01.
  - **Change:** A standard-library Okapi BM25 over the shared chunks with identifier-preserving tokenization; build_index, retrieve and index_stats; capabilities declared.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKA; an exact error-code query ranks its clause first; hand-computed BM25 scores match; unsupported ACL filtering is declared, not faked (the neutral filter is the harness wrapper).
  - **Evidence:** E-B04-002, E-B04-003; hand-computed BM25, exact error-code queries rank their clause first, ACL and budget enforced; planted defects killed.

<a id="b04-t01-02"></a>

- [x] **B04-T01.02 — R1 dense arm and approximate-vs-exact check**
  - **Files:** `palladion-benchmark/benchmark/adapters/dense.py`, `palladion-benchmark/tests/test_dense.py`.
  - **Depends:** B04-T01.01, B04-T01.05, OQ04, BADR-0025.
  - **Change:** The pinned embedding model through fastembed and a Qdrant HNSW collection in the benchmark's own server; exact k-NN comparison on a representative subset; embedding revision and file digest verified at load.
  - **Proof:** INTEGRATION; BG-ADAPTER; ANN recall against exact search is measured and recorded; the embedding revision is pinned; a tampered model file is refused.
  - **Evidence:** E-B04-002, E-B04-003; pinned embedding model verified by digest, Qdrant HNSW collection, ANN recall measured at build (25 queries, K=10: mean 1.0, min 1.0), server version recorded.

<a id="b04-t02-01"></a>

- [x] **B04-T02.01 — R2 hybrid fusion and the two metadata conditions**
  - **Files:** `palladion-benchmark/benchmark/adapters/hybrid.py`, `palladion-benchmark/tests/test_hybrid.py`.
  - **Depends:** B04-T01.02.
  - **Change:** R0+R1 reciprocal-rank fusion with a pinned constant, exact-key channel reported separately, and C1 text-only versus C2 evidence-governed wrappers over the shared harness filter.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; C1 and C2 differ only in the neutral filter; the fusion constant appears in the manifest; fusion matches a hand-computed example.
  - **Evidence:** E-B04-002, E-B04-003; RRF matches a hand-computed example, exact-key chunks reported separately, C1 and C2 differ only in the filter.

<a id="b04-t02-02"></a>

- [x] **B04-T02.02 — R3 reranker arm and token-budget enforcement**
  - **Files:** `palladion-benchmark/benchmark/adapters/hybrid.py`, `palladion-benchmark/tests/test_hybrid.py`.
  - **Depends:** B04-T02.01, OQ05, BADR-0025.
  - **Change:** The pinned cross-encoder over R2 candidates with its revision and digest verified; both evidence token budgets enforced by the shared enforcer.
  - **Proof:** INTEGRATION; BG-FAIR; two arms at the same budget deliver within one chunk of the same counted words; an over-budget bundle is truncated and flagged; the reranker's language limit is recorded.
  - **Evidence:** E-B04-002; pinned cross-encoder verified by digest and used over the fused top 30; equal budgets deliver within one chunk; language caveat recorded.

<a id="b04-t03-03"></a>

- [x] **B04-T03.03 — Isolated Palladion runtime for R7a**
  - **Files:** `palladion-benchmark/scripts/palladion_runtime.py`, `palladion-benchmark/tests/test_palladion_runtime.py`.
  - **Depends:** B04-T03.01, BADR-0016, BADR-0025.
  - **Change:** Create a detached git worktree of Palladion at a recorded commit under the benchmark's artifacts, a dedicated runtime root, Qdrant collection and port (its own Qdrant on 17333, never 16333), seed it with Palladion's own seed code, read the tokens it writes only inside the adapter process, start and stop only the processes it started, and record the commit, mode, graph setting and embedding and reranker pins read from that worktree's source.
  - **Proof:** INTEGRATION; BG-REPRO, BG-SECURITY; Palladion's default root and port are untouched (checked before and after); a dirty source tree is refused or recorded; tokens never reach a log, manifest or artifact.
  - **Evidence:** E-B04-002, E-B04-003; detached worktree at 6444345, own root and collection, Palladion's defaults unchanged before and after, demo sources revoked and proven unretrievable, models verified before copy.

<a id="b04-t03-01"></a>

- [x] **B04-T03.01 — R7a Palladion retrieval adapter over its HTTP API**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/tests/test_palladion_adapter.py`.
  - **Depends:** B01-T03.01, B04-T01.03, OQ03.
  - **Change:** Authenticated calls to Palladion's search interface with the principal injected by the harness and an explicit principal-to-case mapping; no import of Palladion code. Candidates carry the published document id through a revision-to-document table written at upload. A response whose status is UNAVAILABLE or DEGRADED is a run state (NOT_RUN or INVALID_RUN with its code), never an empty list. Palladion's search takes only case, query, mode and a limit of at most 12, no clock and no token budget: the adapter truncates by counted words on the harness side, marks K=20 and any frozen-clock requirement it cannot honor as NOT_RUN or FEATURE_NOT_SUPPORTED, and declares the differences. Client timeouts and concurrency are bounded.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-SECURITY, BG-FAIR; a static scan finds no palladion package import; a real call returns candidates mapped to published documents; a K=20 request is flagged, not silently capped; an UNAVAILABLE or DEGRADED body and an unreachable server are NOT_RUN or INVALID_RUN, never a zero score; a reranked request against a server started without the reranker is refused.
  - **Evidence:** E-B04-002, E-B04-003; real calls over HTTP, no Palladion import, K above 12 refused, unavailable, partial and unknown responses are run states, passages verified against published bytes.

<a id="b04-t03-02"></a>

- [x] **B04-T03.02 — Load the published corpus into Palladion through its authenticated source interface**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/tests/test_palladion_adapter.py`.
  - **Depends:** B04-T03.01, B04-T03.03, B02-T03.01.
  - **Change:** Upload each published document as a seeded uploader and approve it as a distinct seeded approver through Palladion's source and approval endpoints, mirroring the fixture registry's states that its interface can express (draft stays unapproved; retired and withdrawn states are declared gaps); split any document above Palladion's size limits and record how; wire per-case live observations only where the interface allows, otherwise declare the gap.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; read back counts of approved revisions against the corpus manifest and verify through search that each approved document is reachable; a draft is never approved; a mismatch fails the load.
  - **Evidence:** E-B04-002; full 1,200-document load (1,164 approved, 9 of them then revoked; 36 left as draft), read back by counts and sampled passages; drafts never approved.

<a id="b04-t04-01"></a>

- [x] **B04-T04.01 — Index build entry point**
  - **Files:** `palladion-benchmark/scripts/build_indices.py`, `palladion-benchmark/benchmark/track_a.py`, `palladion-benchmark/tests/test_build_indices.py`.
  - **Depends:** B04-T02.02, B04-T01.05, BADR-0025.
  - **Change:** Build per-arm indexes for a snapshot from the published namespace only, in common-chunk mode (shared parser and boundaries); native-ingestion mode is deferred (BADR-0025). Record time, size, tokens, extraction failures and lost tables; a failed build is recorded.
  - **Proof:** SMOKE; BG-REPRO; rebuild from the same manifest yields matching counts; a failed build is recorded rather than skipped; the entry point refuses a snapshot root that holds annotation namespaces as its corpus argument.
  - **Evidence:** E-B04-002; build records time, sizes, words and failures; a failed build is recorded and fails the command; the snapshot root is refused as the corpus.

<a id="b04-t04-02"></a>

- [x] **B04-T04.02 — Track A runner and scoring entry point**
  - **Files:** `palladion-benchmark/scripts/run_track_a.py`, `palladion-benchmark/scripts/score_track_a.py`, `palladion-benchmark/benchmark/track_a.py`, `palladion-benchmark/tests/test_run_track_a.py`.
  - **Depends:** B04-T04.01, B04-T03.01, B01-T04.01, B03-T02.01, B03-T03.02, B03-T05.01, B03-T07.01.
  - **Change:** Run arms on a split with intention-to-treat accounting through the real Runner, refuse the test split without the recorded seal, record K, budget and condition in each manifest, write run artifacts with manifests, and score a run directory into scorecards and a states table.
  - **Proof:** SMOKE; BG-TRACKA; the artifacts contain no gold field; arms not run appear with a reason; the test split is refused; a run scored at a different K is rejected.
  - **Evidence:** E-B04-002; real Runner, ITT records, K, budget and condition in manifests, test split refused, arm notes kept as ledger flags, scoring entry point.

<a id="b04-t04-03"></a>

- [x] **B04-T04.03 — Result validation entry point**
  - **Files:** `palladion-benchmark/scripts/validate_results.py`, `palladion-benchmark/benchmark/results_check.py`, `palladion-benchmark/tests/test_validate_results.py`.
  - **Depends:** B04-T04.02.
  - **Change:** Check schema, call and token budgets, gold and secret leakage by scanning artifacts for every gold string, question-id family and token, manifest and ledger hashes, and that the run read only the published namespace and the split's own annotation file (recorded by the runner).
  - **Proof:** INTEGRATION; BG-REPRO, BG-FAIR; a run directory containing planted gold text, a planted token or a record of a locked-test read is rejected; a clean directory passes.
  - **Evidence:** E-B04-002, E-B04-003; clean runs pass; planted gold text, gold keys, test-namespace read, token, over-K and over-budget bundles, ledger holes and manifest tampering are each rejected.

<a id="b04-t05-01"></a>

- [x] **B04-T05.01 — Track A pilot measurement**
  - **Files:** `palladion-benchmark/scripts/score_track_a.py`, `palladion-benchmark/benchmark/eval/score_run.py`, `palladion-benchmark/tests/test_score_run.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B04-T04.03, B02-T07.02.
  - **Change:** Withdraw the three synthesis questions whose gold omits policies the question asks for (BADR-0026, BR29) through a recorded exclusion list the scorer applies, so every score states 97 of 100 questions; then run R0, R1, R2, R3 and R7a on the pilot (smoke partition only; the S-tier test partition stays unread), inspect failures by hand, and record scores with denominators; pilot results are excluded from held-out claims.
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-METRIC; exact commands, counts and raw failures preserved; no superiority claim.
  - **Evidence:** E-B04-005; pilot-c2 and pilot-c1 on the smoke split, 500 of 500 pairs each, both pass the validator, 97 questions scored after the BADR-0026 withdrawal; no ranking claim.

### Atomic tasks — B05

<a id="b05-t07-01"></a>

- [x] **B05-T07.01 — Answer-gold sidecar and structured answer contract**
  - **Files:** `palladion-benchmark/benchmark/fixtures/answer_gold.py`, `palladion-benchmark/benchmark/fixtures/manifest.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/scripts/generate_data.py`, `palladion-benchmark/tests/test_answer_gold.py`.
  - **Depends:** B02-T04.01, B02-T07.01, B03-T01.01, BADR-0028.
  - **Change:** Derive from the hidden world an evaluator-only answer-gold file per split (own digest, in the annotation namespace; the question file and the label-audit digests are untouched): claim units with an id, a closed kind, required or forbidden and the evidence slot they rest on; a closed action; the policy outcome; the applicable version ids and the as-of basis. Add optional structured fields to CaseResponse (action, policy outcome, version ids, claim kinds) with defaults so every existing arm and test is unchanged, define the answer citation syntax (document@version#clause, mapped to the published clause or character locator) and the generator's JSON answer schema.
  - **Proof:** INTEGRATION; BG-GOLD, BG-SECURITY; every answerable question has a required claim unit and every question with a policy outcome has a closed outcome; the question file digest and the audit's gold digests do not change; the answer-gold is refused by the published-view reader and a planted copy in a run directory is rejected by the validator.
  - **Evidence:** E-B05-002, E-B05-003; the answer-gold derives for all 100 questions, its digest binds the questions, the question file and audit digests are unchanged.

<a id="b05-t09-01"></a>

- [x] **B05-T09.01 — Generator fault mapping, prompt barrier and cancellation**
  - **Files:** `palladion-benchmark/benchmark/generator.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/tests/test_generator_pool.py`, `palladion-benchmark/tests/test_runner.py`.
  - **Depends:** B01-T05.01, B01-T05.02, B01-T04.01, B05-T07.01, BADR-0028.
  - **Change:** Map each generator failure code to a run state and origin (rate limit after retries and provider HTTP faults: INVALID_RUN from the provider; budget exhausted and disabled: NOT_RUN from the harness) instead of an arm contract violation; keep the total rate-limit wait below the case deadline; check a cancel flag before every dispatch and every record write so a timed-out worker makes no further call and writes nothing; screen every prompt message with the arm-visible screen; keep the full prompt text of each call so the validator can scan it.
  - **Proof:** UNIT; BG-FAIR, BG-SECURITY; a stub transport that sleeps past the deadline is followed by no call and no record; a prompt carrying a gold-marked string is refused; each code maps to its state and origin.
  - **Evidence:** E-B05-002, E-B05-003; faults are classified by who caused them, a refused call writes nothing, every prompt is screened and kept.

<a id="b05-t01-01"></a>

- [x] **B05-T01.01 — Citation metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/citations.py`, `palladion-benchmark/tests/test_citations.py`.
  - **Depends:** B03-T01.01, B02-T04.01, B05-T07.01.
  - **Change:** Validity, accessibility, temporal applicability, completeness, granularity, diversity and fabrication, computed against the delivered evidence bundle and the published registry (a citation outside the bundle is a fabrication, and the answer's own status field is recorded, never trusted); an entailment hook that reads labels from the label store and counts unlabelled pairs; stability is NOT_RUN in B05 (it needs two index generations); precision and recall with visible denominators; granularity reported per arm because arms return different locator kinds.
  - **Proof:** UNIT; BG-METRIC; a fabricated locator is detected; a citation to a document that was not delivered is a fabrication; uncited false claims are counted separately; unlabelled entailment pairs are counted, not scored.
  - **Evidence:** E-B05-002, E-B05-003; fabrication, bundle, access, authority, version, granularity and entailment counts with denominators.

<a id="b05-t01-02"></a>

- [x] **B05-T01.02 — Claim-level scoring and unsupported-directive rate**
  - **Files:** `palladion-benchmark/benchmark/eval/claims.py`, `palladion-benchmark/tests/test_claims.py`.
  - **Depends:** B05-T01.01, B05-T07.01.
  - **Change:** Score the answer's claim units against the answer-gold (closed kinds, required and forbidden): correctness at the as-of time, support, completeness, contradiction, action correctness and usefulness, all deterministic; compute the unsupported operational directive rate and correct substantive-answer coverage, the co-primary Track B endpoints, each both intention-to-treat (non-completion counts against coverage, and as unknown in a worst-case directive bound) and conditional on completion, with the zero-failure upper bound and the denominators stated; no judge is used for an action.
  - **Proof:** UNIT; BG-METRIC; a planted unsupported refund directive is counted and a correct supported answer is not; a timed-out pair lowers intention-to-treat coverage and widens the worst-case directive bound; coverage and directive rate are reported together.
  - **Evidence:** E-B05-002, E-B05-003; both accountings of the two endpoints; a planted unsupported directive is counted.

<a id="b05-t02-01"></a>

- [x] **B05-T02.01 — Temporal and policy scoring**
  - **Files:** `palladion-benchmark/benchmark/eval/policy.py`, `palladion-benchmark/tests/test_policy.py`.
  - **Depends:** B05-T07.01, B02-T01.02.
  - **Change:** Version-selection accuracy, as-of completeness, retroactivity, future-policy leakage, wrong-vintage action rate, exact outcome accuracy, missing-input recall and override attempts, by comparing the answer's declared version ids and outcome with the stored answer-gold; the scorer never calls the generator's own resolver. The oracle-tool condition belongs to Track C (B07-T08.01) because Track B arms have no policy tool.
  - **Proof:** UNIT; BG-METRIC, BG-GOLD; every as-of basis is scored from the declared basis, not recency; a planted change to the resolver leaves the scores unchanged.
  - **Evidence:** E-B05-002, E-B05-003; scored from the declared basis and the stored gold; the resolver is never called.

<a id="b05-t03-01"></a>

- [x] **B05-T03.01 — Abstention, selective prediction and loss**
  - **Files:** `palladion-benchmark/benchmark/eval/abstention.py`, `palladion-benchmark/configs/evaluation.yaml`, `palladion-benchmark/tests/test_abstention.py`.
  - **Depends:** B03-T04.01, B05-T01.02, B05-T02.01, BADR-0028.
  - **Change:** False-answer and false-abstention rates, selective risk and coverage at the decision point, reason accuracy, partial utility and the weighted loss matrix with an event classifier and a fixed sweep grid (both in the ADR, before any measurement); AURC is not computed in B05 because no harness-observed confidence score is defined; the metric groups for citation, policy, abstention and track metrics are added to evaluation.yaml.
  - **Proof:** UNIT; BG-METRIC; an always-abstain system scores poorly on coverage and partial utility; the winner is reported as conditional when the sweep flips it; every metric of the cards sits in exactly one group.
  - **Evidence:** E-B05-002, E-B05-003; false answer and abstention, selective figures, events and the weight sweep.

<a id="b05-t04-01"></a>

- [x] **B05-T04.01 — Scoring rubric and annotation guide**
  - **Files:** `palladion-benchmark/docs/scoring_rubric.md`, `palladion-benchmark/docs/annotation_guide.md`.
  - **Depends:** B05-T01.01, B05-T02.01, B05-T03.01.
  - **Change:** Exact labeler rubrics with examples, the blinded fields (arm identity, generator model, judge output), a sampling seed, who labels and how many (the owner or the coordinator under delegation; agreement is never reported as human against human), adjudication and agreement procedures.
  - **Proof:** DOC; BG-GOLD; each metric has a rubric entry; a labeler who knows only the blinded packet can apply it to the pilot.
  - **Evidence:** E-B05-002; scoring_rubric.md and annotation_guide.md cover every metric.

<a id="b05-t04-02"></a>

- [x] **B05-T04.02 — Blinded labeling workflow and judge audit**
  - **Files:** `palladion-benchmark/benchmark/eval/judge_audit.py`, `palladion-benchmark/tests/test_judge_audit.py`.
  - **Depends:** B05-T04.01, B01-T05.01.
  - **Change:** A label store with fixed source precedence (deterministic, then human, then judge) that refuses a lower source overwriting a higher one; blinded sampling for human labels; an LLM judge as a secondary check with exposed prompts kept outside run directories, at least two judges with distinct model ids and family overlap disclosed (the approved pool has only two families), judge agreement against human labels reported with denominators before judge output counts; human-judge disagreement reporting. Judge calls need the owner's authorization; tests use injected transports.
  - **Proof:** UNIT; BG-METRIC; a judge write cannot replace a deterministic or human label; disagreement is reported with denominators; judge prompts never appear in a run directory.
  - **Evidence:** E-B05-002, E-B05-003; precedence, blinded sampling, judges as injected callables; no live judge call.

<a id="b05-t05-01"></a>

- [x] **B05-T05.01 — Track B runner**
  - **Files:** `palladion-benchmark/benchmark/track_b.py`, `palladion-benchmark/scripts/run_track_b.py`, `palladion-benchmark/tests/test_track_b.py`.
  - **Depends:** B04-T04.02, B05-T07.01, B05-T09.01, B01-T05.02.
  - **Change:** Compose a retriever arm and the shared generator into a system arm the Runner already dispatches: the same generator, prompt template, JSON answer schema, evidence budget (whitespace words) and runtime gate for every retriever (every cited or used id must come from the delivered bundle, truncation is flagged); condition C2 for all arms with C1 as a sensitivity run, one named R7a variant per run; per-call model recorded and a pair whose arms ran on different models flagged; questions that assign_models leaves unassigned are NOT_RUN for every arm; with null token budgets the pilot is single-model and says so; prompts and generation records are written to the run directory; a live call needs the explicit enable flag and the owner's authorization.
  - **Proof:** SMOKE; BG-TRACKB, BG-FAIR; a stub-transport run over R2, R3 and R7a-shaped arms completes for every question; a pair whose arms ran on different models is flagged; a gold-marked prompt is refused; no hidden gold at generation time; no live call is made without the flag.
  - **Evidence:** E-B05-002, E-B05-003; one prompt, generator and gate for every arm through the real Runner; 261 of 261 on the real corpus with the offline stand-in.

<a id="b05-t08-01"></a>

- [x] **B05-T08.01 — Track B scoring entry point and validator branch**
  - **Files:** `palladion-benchmark/scripts/score_track_b.py`, `palladion-benchmark/benchmark/eval/score_answers.py`, `palladion-benchmark/benchmark/results_check.py`, `palladion-benchmark/benchmark/analysis/tables.py`, `palladion-benchmark/tests/test_score_answers.py`.
  - **Depends:** B05-T01.02, B05-T02.01, B05-T03.01, B05-T05.01, B03-T06.01, B04-T04.03.
  - **Change:** A scorer that reads a Track B run directory (answers, ledger, generation records, prompts, manifests), recomputes citation and status fields from the delivered bundle, applies the withdrawn-question list and writes a scorecard with intention-to-treat and conditional tables side by side; a controlled_qa branch of the validator that checks answer schema, per-call model records, budget counts, prompts for gold, and that every cited id was delivered.
  - **Proof:** INTEGRATION; BG-TRACKB, BG-REPRO; a clean stub run passes and is scored; planted defects (gold in a prompt, a prompt marker, an over-budget prompt, delivered ids that differ from the prompt, a missing generation record, a model outside the pool, a dropped pair) are each rejected for their own reason; a citation outside the bundle is a valid run and is counted as a fabrication by the scorer.
  - **Evidence:** E-B05-002, E-B05-003; clean runs pass and are scored; planted defects are each rejected.

<a id="b05-t06-01"></a>

- [x] **B05-T06.01 — Track B pilot measurement with the real provider**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B05-T08.01, B05-T04.02.
  - **Change:** A bounded first pass authorized by the owner (BADR-0029): R2 and R3 only, a seeded stratum-balanced subset of 8 questions, at most 20 generator calls in the recorded model order, 700 completion tokens, paced, no judge call. Stored retrieval is replayed through the real arms so only generator calls are live; record quota, attempts and failures; outputs are single-run and descriptive. R7a, the full smoke split and any further live use need a new owner instruction.
  - **Proof:** MEASUREMENT; BG-TRACKB; real-provider responses used; failures and rate-limit events preserved; no confirmatory claim.
  - **Evidence:** E-B05-005; 16 of 16 real qwen calls on R2 and R3 over 8 questions, 15 pairs OK and 1 invalid, no rate limit and no failover; descriptive, single run, no ranking claim; R7a not run.

### Atomic tasks — B06

<a id="b06-t00-01"></a>

- [x] **B06-T00.01 — Additive contract extensions for graph arms**
  - **Files:** `palladion-benchmark/benchmark/run_manifest.py`, `palladion-benchmark/benchmark/track_a.py`, `palladion-benchmark/benchmark/eval/cost_latency.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/benchmark/results_check.py`, `palladion-benchmark/tests/test_graph_contracts.py`.
  - **Depends:** B04-T04.02, B04-T04.03, B05-T08.01.
  - **Change:** Add, without changing any existing field, the arm ids R4 to R7b to the Track A arm list; an optional comparator pin (repository, commit, lock digest, interpreter) and native-configuration block in the manifest; an offline cost record with extraction calls, tokens and storage beside build time; and an optional relation field on a candidate. Old manifests, ledgers and results still validate unchanged.
  - **Proof:** UNIT; BG-ADAPTER, BG-REPRO; an old run directory validates byte for byte as before; a graph run without its pin or cost is rejected for that reason; the new fields appear in no gold-visible file.
  - **Evidence:** E-B06-002; additive contracts: pin, extraction cost, relation field; an old run directory validates unchanged.

<a id="b06-t00-02"></a>

- [x] **B06-T00.02 — Comparator worker and counting LLM proxy**
  - **Files:** `palladion-benchmark/benchmark/adapters/worker.py`, `palladion-benchmark/benchmark/llm_proxy.py`, `palladion-benchmark/comparators/protocol.py`, `palladion-benchmark/tests/comparator_stub.py`, `palladion-benchmark/tests/test_comparator_worker.py`, `palladion-benchmark/tests/test_llm_proxy.py`.
  - **Depends:** B06-T00.01, B01-T05.01.
  - **Change:** Run each comparator as a subprocess in its own environment behind a line-delimited JSON protocol (build, retrieve, stats, stop), with a local proxy in front of its LLM client that counts every call and token, enforces the call cap, token cap, pace and model list, and refuses everything once spent. A timed-out worker is killed and its spend is still counted (BR14). No key is written to a log, a record or the worker's environment dump.
  - **Proof:** INTEGRATION; BG-FAIR, BG-ADAPTER; a fake comparator that loops on calls is stopped at the cap; a hung worker is killed and the pair is a timeout, not a zero; a planted key never appears in any file; the proxy rejects a model outside the approved list.
  - **Evidence:** E-B06-002; worker and counting proxy: a runaway comparator is stopped at the cap, a hung one is killed with its children, the key never reaches it.

<a id="b06-t00-03"></a>

- [x] **B06-T00.03 — Comparator pins, approved downloads and isolated environments**
  - **Files:** `palladion-benchmark/scripts/comparators.py`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/tests/test_comparators.py`.
  - **Depends:** B06-T00.01, OQ14.
  - **Change:** For each of HippoRAG 2, GraphRAG and LightRAG: fetch the upstream source at a commit the owner approved by name, source and size, verify the repository identity and commit at run time, create an isolated uv environment on an interpreter the upstream supports, and record the lock digest and interpreter in the manifest. Nothing is downloaded before the owner approves that artifact.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-REPRO; a wrong commit or wrong repository identity is refused; an unapproved artifact is refused; the recorded pin reproduces the environment.
  - **Evidence:** E-B06-002; the three approved checkouts verify by commit, the environments are described by lock digest and interpreter.

<a id="b06-t01-01"></a>

- [x] **B06-T01.01 — R4 HippoRAG 2 adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/hipporag2.py`, `palladion-benchmark/comparators/hipporag2/worker.py`, `palladion-benchmark/tests/test_hipporag2.py`.
  - **Depends:** B06-T00.02, B06-T00.03, OQ06.
  - **Change:** Official pipeline at the pinned commit through the worker; its own indexing, extraction and retrieval, never our Qdrant search. Record native configuration and deviations, the query-time model calls (counted, or disabled and recorded), indexing cost and the embedding model. The graph input is the published document text only (no world relation, no supersession edge); native outputs are mapped to the shared 120-word chunks; ACL and as-of filtering are declared UNSUPPORTED, not simulated.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; offline with a stub LLM and the real upstream retrieval code; a planted gold phrase in a document is rejected before indexing; the manifest holds the pin; unsupported affordances are listed, not zero.
  - **Evidence:** E-B06-002, E-B06-003; the real HippoRAG 2 index and retrieve run offline behind the proxy; no live call.

<a id="b06-t02-01"></a>

- [x] **B06-T02.01 — R5 GraphRAG Local adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/graphrag.py`, `palladion-benchmark/comparators/graphrag/worker.py`, `palladion-benchmark/tests/test_graphrag.py`.
  - **Depends:** B06-T00.02, B06-T00.03, OQ06.
  - **Change:** Official local query mode at the pinned commit through the worker, with the same input, mapping, cost, ACL and as-of rules as R4. Global and DRIFT are exploratory modes with their own conditions and are not built in this phase (BADR-0031); nothing is merged into the R5 row.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; same controls as R4; a community or entity summary that quotes a document the principal may not read is flagged by a planted probe.
  - **Evidence:** E-B06-002, E-B06-003; the real GraphRAG standard index and local context builder run offline behind the proxy; no live call.

<a id="b06-t03-01"></a>

- [x] **B06-T03.01 — R6 LightRAG adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/lightrag.py`, `palladion-benchmark/comparators/lightrag/worker.py`, `palladion-benchmark/tests/test_lightrag.py`.
  - **Depends:** B06-T00.02, B06-T00.03, OQ06.
  - **Change:** Official hybrid mode at an upstream commit whose repository identity is verified at run time, through the worker, with the same input, mapping, cost, ACL and as-of rules as R4.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; same controls as R4; the repository identity and commit are verified when the arm is built.
  - **Evidence:** E-B06-002, E-B06-003; the real LightRAG hybrid retrieval runs offline behind the proxy; no live call.

<a id="b06-t04-01"></a>

- [x] **B06-T04.01 — R7b status at the pinned Palladion commit**
  - **Files:** `palladion-benchmark/benchmark/registry.py`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/docs/development/PALLADION_FIXES.md`, `palladion-benchmark/tests/test_graph_arms.py`.
  - **Depends:** B04-T01.04, B04-T03.02, B06-T00.03.
  - **Change:** At 6444345 Palladion holds only EXCEPTION_TO links that its own code creates in-process, and no HTTP route creates links, so an HTTP-only arm cannot give it a graph. Declare R7b unsupported at the pin (a declared absence, FEATURE_NOT_SUPPORTED, never a zero), keep Neo4j and the compose service out of this phase, and record PF07 in PALLADION_FIXES.md (a route that registers links from published text only). The arm runs in a later card once PF07 lands and a pin that differs from R7a only by graph code exists.
  - **Proof:** UNIT; BG-ADAPTER; R7b resolves to FEATURE_NOT_SUPPORTED with its reason in every run that names it; it is never scored as zero; PF07 is written with what, where, why, how and proof.
  - **Evidence:** E-B06-002; R7b is FEATURE_NOT_SUPPORTED at the pin, never a zero; PF07 written.

<a id="b06-t05-01"></a>

- [x] **B06-T05.01 — Graph-specific metrics that the data supports**
  - **Files:** `palladion-benchmark/benchmark/eval/graph_metrics.py`, `palladion-benchmark/tests/test_graph_metrics.py`.
  - **Depends:** B03-T03.02, B06-T00.01.
  - **Change:** Cross-document hop completion, edge provenance validity, false-association rate and traversal cost per useful slot, each with perfect, empty and shuffled controls and a hand-computed case. Relationship precision and recall, typed-traversal correctness, wrong-node merge and hub pollution are declared UNDEFINED with the missing data named (no relation output, no entity gold, no degree), not estimated.
  - **Proof:** UNIT; BG-METRIC; a planted unsupported edge raises the false-association rate; an undefined metric prints as undefined with its reason; small denominators are printed beside every figure.
  - **Evidence:** E-B06-002; four graph metrics with controls, four declared undefined.

<a id="b06-t06-01"></a>

- [x] **B06-T06.01 — Cold-state Track A run for graph arms on a matched subset**
  - **Files:** `palladion-benchmark/benchmark/subset.py`, `palladion-benchmark/scripts/build_subset.py`, `palladion-benchmark/scripts/run_graph_arms.py`, `palladion-benchmark/tests/test_subset.py`, `palladion-benchmark/tests/test_run_graph_arms.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B06-T01.01, B06-T02.01, B06-T03.01, B06-T04.01, B06-T05.01, OQ14.
  - **Change:** Run R4 to R6 from cold on a seeded subset of S (about 100 documents chosen by a recorded rule, with the questions they support) under the owner's call, token and model limits, and run R0 to R3 and R7a on the same subset so the comparison is matched. Cold means the working directory and every cache cleared and recorded. Report indexing time, extraction calls, tokens and storage beside query cost; label it a pilot on the smoke split; no ranking claim. The full S tier is not run on the free tier (estimated 4 million tokens and 8 hours per system).
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-FAIR; the subset rule and its limits are recorded; indexing cost is reported with query cost; unsupported capabilities and R7b are listed; calls never exceed the owner's cap.
  - **Evidence:** E-B06-004, E-B06-005; closed with limits by the owner (BADR-0037): R6 63 of 103 chunks over 410 calls, R4 and R5 not attempted, R0 to R3 matched on the subset, no ranking claim.

### Atomic tasks — B07

<a id="b07-t00-06"></a>

- [x] **B07-T00.06 — Counting proxy: tool-call allowance for agent arms**
  - **Files:** `palladion-benchmark/benchmark/llm_proxy.py`, `palladion-benchmark/tests/test_llm_proxy.py`.
  - **Depends:** B06-T00.02.
  - **Change:** The proxy refuses every request that carries tools, so no agent arm can be counted or capped. Add an opt-in per-run allowance (off by default, so the graph comparators' paths are unchanged) that accepts the tool-calling parameters (tools, tool_choice, parallel_tool_calls), counts every tool call a reply requests, and refuses once a stated tool-call cap is reached; the call, token, completion and model caps apply exactly as before.
  - **Proof:** UNIT; BG-ADAPTER, BG-FAIR; with the allowance off a tool request is still refused; with it on, replies' tool calls are counted and the cap stops the next call; a request with an unknown parameter is still refused.
  - **Evidence:** E-B07-002; tool-call allowance in the counting proxy.

<a id="b07-t00-01"></a>

- [x] **B07-T00.01 — Palladion model transport for counted evaluation runs**
  - **Files:** `palladion-benchmark/docs/development/ADR_LOG.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Palladion files:** `palladion/src/evidence_agent/agent/llm.py`, `palladion/scripts/serve.py`, `palladion/tests/test_llm_transport.py`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B04-T03.02, B07-T00.06, BADR-0038.
  - **Change:** Palladion's model client sends every call to the provider's public address with the key from its own .env, so a run could neither be counted nor capped by the benchmark. Give the client an optional base URL accepted only for a loopback host (the default stays the provider), let the key come from a named environment variable instead of a file copy, make the completion cap and the per-request deadline launcher parameters (defaults unchanged), and give the launcher a settings-file argument. Ordinary serving is byte-identical. Each change is written as a Palladion ADR first.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-SECURITY; a non-loopback base URL is refused; the default address is unchanged; a message sent through the benchmark's counting proxy reaches a fake provider and the proxy's book counts every call; the key appears in no log, argument list or file.
  - **Evidence:** E-B07-002; Palladion 4af66d6 (ADR-0099): loopback-only counted transport.

<a id="b07-t00-02"></a>

- [x] **B07-T00.02 — Palladion evaluator mode: critic-off arm and evaluator fields**
  - **Files:** `palladion-benchmark/docs/development/ADR_LOG.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Palladion files:** `palladion/src/evidence_agent/agent/services.py`, `palladion/src/evidence_agent/agent/loop.py`, `palladion/src/evidence_agent/api/schemas.py`, `palladion/scripts/serve.py`, `palladion/tests/test_evaluator_mode.py`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B07-T00.01.
  - **Change:** Today the critic-off arm (the evaluator control B5) exists only inside Palladion's own Python study, so E3 has no HTTP path. Add a launcher option that starts the server in an evaluator mode with an explicit acknowledgement flag, wires the chosen evaluator arm into every case runtime (server wiring, never a request field), and, only in that mode, adds an evaluator block to the message response: the arm, model calls and tokens by role, the critic's findings and countersearch queries, the initial draft digest and each claim's closed kind. Default serving, its response schema and its 'no serving bypass' statement are unchanged; gate, ACL, authority, parser and time stay mandatory. E3 is Palladion's own B5 (critic removed, final gate kept), so a policy or operational claim the gate releases only after review is reported unavailable, and that is disclosed.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKC; with the arm set the trace holds no critic call and the default holds one; the default response is byte-identical to before; a request carrying an arm field is rejected; the capability report still lists every bypass as unsupported.
  - **Evidence:** E-B07-002; Palladion 4af66d6 (ADR-0100): evaluator mode and block.

<a id="b07-t00-03"></a>

- [x] **B07-T00.03 — Palladion evaluation clock**
  - **Files:** `palladion-benchmark/docs/development/ADR_LOG.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Palladion files:** `palladion/src/evidence_agent/retrieval/evidence.py`, `palladion/src/evidence_agent/memory/packet.py`, `palladion/src/evidence_agent/agent/preflight.py`, `palladion/src/evidence_agent/agent/services.py`, `palladion/scripts/serve.py`, `palladion/tests/test_evaluation_clock.py`, `palladion/docs/development/ADR_LOG.md`, `palladion/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B07-T00.02.
  - **Change:** Palladion reads the wall clock for live-observation freshness, the evidence ledger, the continuity packet and preflight, so the same case answers differently on different days, while protocol 3.1 item 6 freezes the evaluation time. In evaluator mode only, pass one clock from the launcher through the ledger, the packet builder, preflight and the gateway (an explicit argument, no global override); the default stays the wall clock.
  - **Proof:** INTEGRATION; BG-FAIR, BG-REPRO; the same case sent at two different real times gives an identical answer, freshness verdict and trace under a fixed clock; without the option the wall clock is still used.
  - **Evidence:** E-B07-002; Palladion 4af66d6, eec4ba5 (ADR-0101): registry-owned evaluation clock; reported to the owner.

<a id="b07-t00-04"></a>

- [x] **B07-T00.04 — One Palladion pin for R7a, E3 and E4**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/scripts/palladion_runtime.py`, `palladion-benchmark/scripts/palladion_aliases.py`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/tests/test_palladion_runtime.py`.
  - **Depends:** B07-T00.03, B04-T03.02, B06-T04.01.
  - **Change:** Choose the Palladion commit that carries the three changes above as the single pin for R7a, E3 and E4, rebuild the isolated worktree and runtime at it, and rerun the R7a smoke. Re-evaluate the alias and principal workarounds of BADR-0027 against PF02 and PF05 and drop only those the new version makes unnecessary. Results recorded at 6444345 keep that pin and are history; they are not rescored.
  - **Proof:** SMOKE; BG-ADAPTER, BG-REPRO; the worktree commit equals the pin and a dirty tree is refused; an R7a retrieval run returns candidates mapped to published documents for the subset questions; the manifest names the new pin and the old runs still validate.
  - **Evidence:** E-B07-002; BADR-0041: one pin eec4ba5.

<a id="b07-t00-05"></a>

- [x] **B07-T00.05 — Pins and approved environments for LangChain, LangGraph and Google ADK**
  - **Files:** `palladion-benchmark/scripts/comparators.py`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/tests/test_comparators.py`.
  - **Depends:** B06-T00.03, B07-T00.04, OQ14.
  - **Change:** Same pattern as the graph comparators: for each framework, an exact version the owner approves by name and size, an isolated uv environment on an interpreter its wheels support, the lock digest and interpreter in the manifest, and no download before approval. Google ADK is only recorded (its use is conditional, B07-T03.01).
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-REPRO; an unapproved package or a wrong version is refused; the environment reproduces its recorded digest.
  - **Evidence:** E-B07-002; BADR-0040: env-langchain pins; Google ADK not installed.

<a id="b07-t01-01"></a>

- [x] **B07-T01.01 — E0 plain LangChain two-step**
  - **Files:** `palladion-benchmark/benchmark/adapters/langchain.py`, `palladion-benchmark/benchmark/adapters/worker.py`, `palladion-benchmark/benchmark/run_manifest.py`, `palladion-benchmark/scripts/comparators.py`, `palladion-benchmark/comparators/langchain/worker.py`, `palladion-benchmark/tests/test_langchain.py`.
  - **Depends:** B07-T00.05, B04-T04.02, B01-T05.01, B05-T06.01.
  - **Change:** A worker in its own pinned environment indexes the published text with LangChain's standard splitter, an in-memory vector store and the benchmark's embedding model served by the counting proxy, and returns ranked chunks; the benchmark's shared generator, prompt and answer gate then answer (the Track B pattern). Declared a reference implementation, not one algorithm; the component versions and splitter sizes are recorded. One generator call per question, enforced.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKC; the manifest holds the component versions; a second generator call is refused and recorded as a failure; a planted gold phrase in the published text is rejected before indexing.
  - **Evidence:** E-B07-002; E0 proven in the real framework environment.

<a id="b07-t02-01"></a>

- [x] **B07-T02.01 — E1 LangGraph bounded agentic loop**
  - **Files:** `palladion-benchmark/benchmark/adapters/langgraph.py`, `palladion-benchmark/comparators/langchain/worker.py`, `palladion-benchmark/tests/test_langgraph.py`.
  - **Depends:** B07-T01.01, B07-T00.06.
  - **Change:** A LangGraph loop in its own environment with one retriever tool (the E0 retriever) and the same ceilings as the other arms: at most 5 model calls including the final answer, 8 tool calls and the same time limit, counted and capped run-wide by the counting proxy (the tool-call allowance of B07-T00.06) and checked per question from the worker's report. The final reply is parsed by the shared answer schema. Exceeding a ceiling is a recorded failure, never a truncated metric.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; a loop that wants a sixth model call or a ninth tool call is stopped and the case is a recorded failure; the proxy still refuses every tool request on the other arms' paths; counts equal the proxy's book.
  - **Evidence:** E-B07-002; E1 proven, ceilings enforced.

<a id="b07-t03-01"></a>

- [x] **B07-T03.01 — E2 Google ADK with RAG Engine, conditional**
  - **Files:** `palladion-benchmark/benchmark/adapters/google_adk.py`, `palladion-benchmark/benchmark/registry.py`, `palladion-benchmark/tests/test_google_adk.py`.
  - **Depends:** B07-T01.01, OQ07.
  - **Change:** By default E2 is NOT_RUN by configuration with a stated reason (no managed-service access probed; a probe is an external call and needs the owner's approval), and FEATURE_NOT_SUPPORTED for the four-tool and principal-filter set even with access. The adapter never fabricates an answer.
  - **Proof:** UNIT; BG-ADAPTER; the arm reports NOT_RUN with its reason and no score; a configuration that names access but lacks the owner's approval still reports NOT_RUN.
  - **Evidence:** E-B07-002; E2 NOT_RUN with its reason.

<a id="b07-t04-01"></a>

- [x] **B07-T04.01 — E3 and E4 Palladion system adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion_system.py`, `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/benchmark/registry.py`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/tests/test_palladion_system.py`.
  - **Depends:** B07-T00.04, B07-T00.05, B07-T03.01, B07-T00.06, B04-T03.02, OQ11.
  - **Change:** answer, reset_case, report_usage and report_trace over Palladion's message interface (HTTP only). E4 is the default serving path at the pin; E3 is the evaluator-mode critic-off arm (B5), defined by Palladion's own control and disclosed as a distinct treatment. Usage tokens and calls come from the counting proxy's book; Palladion's own counts are kept beside them as self-reported and a divergence is a recorded flag. A GLOBAL_DEADLINE or other verification failure is a run state, never a normal answer. The response's evaluator block feeds the critic and tool-use metrics; fields Palladion does not give are NOT_OBSERVABLE, not zero.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKC; usage equals the proxy's book on a real local Palladion with a fake provider; with the critic off the trace has no critic call; a deadline cut is recorded as such; E3 is never labelled E4.
  - **Evidence:** E-B07-002; E3/E4 on a real server; counts equal the proxy's book.

<a id="b07-t05-01"></a>

- [x] **B07-T05.01 — Multi-turn episodes and time-series update events**
  - **Files:** `palladion-benchmark/benchmark/fixtures/episodes.py`, `palladion-benchmark/benchmark/fixtures/updates.py`, `palladion-benchmark/tests/test_episodes.py`.
  - **Depends:** B02-T04.02, B02-T01.03.
  - **Change:** Episode generator with a deterministic clock, scripted transitions and pseudonymous episode and turn identifiers, partitioned by episode (never by turn) and separately from the question families; 1,000 deterministic document events (create, amend, approve, withdraw, supersede, reclassify, revoke, delete) for the update benchmark; a validity policy on reported facts is not generated (the measure is NOT_OBSERVABLE, BR48). world.py stays the aggregate. The S-tier pilot uses a small subset.
  - **Proof:** UNIT; BG-GOLD; no episode spans two splits; replay is deterministic; identifiers and titles reveal no scenario or expected outcome; the events replay to the same committed state.
  - **Evidence:** E-B07-002; episodes and 1,000-event stream; defect found and fixed.

<a id="b07-t05-02"></a>

- [x] **B07-T05.02 — Memory evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/memory.py`, `palladion-benchmark/benchmark/eval/observable.py`, `palladion-benchmark/tests/test_memory_eval.py`.
  - **Depends:** B07-T05.01.
  - **Change:** Identity continuity, context-anchoring error, provenance preservation, reported-fact validity, live freshness, poisoning promotion, cross-case leakage, packet sufficiency and recovery after correction, each computed from what the answer, the citations and the evaluator block expose. A metric that needs memory contents no interface returns is printed NOT_OBSERVABLE with the reason, never estimated.
  - **Proof:** UNIT; BG-METRIC, BG-SECURITY; a planted promoted user claim and a planted cross-episode recall are counted; perfect, empty and shuffled controls differ; NOT_OBSERVABLE prints beside every score.
  - **Evidence:** E-B07-002; memory measures with NOT_OBSERVABLE.

<a id="b07-t05-03"></a>

- [x] **B07-T05.03 — Update consistency and stale-index exposure metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/cost_latency.py`, `palladion-benchmark/benchmark/fixtures/updates.py`, `palladion-benchmark/tests/test_update_consistency.py`.
  - **Depends:** B07-T05.01, B03-T05.01, B06-T00.01.
  - **Change:** Time-to-consistency and exposure windows after create, amend, withdraw, supersede, ACL revocation and delete events, measured at the reader (a search that must or must not return the item after the event), scored against the as-of rule and the committed source state, separately from retrieval correctness. Index-internal staleness is declared not observed.
  - **Proof:** UNIT; BG-METRIC; a planted lagging reader yields a nonzero window and a consistent one yields zero; a window is never negative.
  - **Evidence:** E-B07-002; exposure windows at the reader.

<a id="b07-t06-01"></a>

- [x] **B07-T06.01 — Critic evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/critic.py`, `palladion-benchmark/tests/test_critic_eval.py`.
  - **Depends:** B05-T01.01, B07-T04.01.
  - **Change:** Objection precision and recall, repair and regression rates, additional retrievals and cost per net prevented directive, and the independent-evidence check, from the evaluator block's initial draft, findings and countersearch. Injected-error pairs (wrong as-of date, fabricated citation, forgotten exception, claimed live state after an outage) come from a scripted main model with the critic blind to the label.
  - **Proof:** UNIT; BG-METRIC; injected-error pairs and clean drafts are both scored; agreement alone is not a metric; the critic's input contains no injected-error label (a planted label is caught).
  - **Evidence:** E-B07-002; critic evaluation, blindness check, reads the real trace.

<a id="b07-t06-02"></a>

- [x] **B07-T06.02 — Tool-use evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/tool_use.py`, `palladion-benchmark/tests/test_tool_use.py`.
  - **Depends:** B01-T03.03, B07-T04.01.
  - **Change:** Tool selection recall, unnecessary invocation, argument validity, result utilization, discovery reversal, boundedness, failure interpretation and escalation, from each system's reported tool calls; a metric that needs arguments a system does not report is NOT_OBSERVABLE for it.
  - **Proof:** UNIT; BG-METRIC; over-budget invocations are counted as failures; a malformed call is surfaced; NOT_OBSERVABLE is never zero.
  - **Evidence:** E-B07-002; tool-use evaluation, reads the real trace.

<a id="b07-t07-01"></a>

- [x] **B07-T07.01 — Mutation and metamorphic specifications with gold**
  - **Files:** `palladion-benchmark/benchmark/fixtures/mutations.py`, `palladion-benchmark/benchmark/fixtures/validation.py`, `palladion-benchmark/tests/test_fixture_integrity.py`.
  - **Depends:** B02-T06.01, B07-T05.01.
  - **Change:** Specify the 19 mutations and 7 metamorphic invariants as data: the base fixture, the exact patch (documents added, revoked or edited, a fact or a clock changed), the gold expectation and the failure metric from protocol 16.1 and 16.2, and a class (fixture only; expressible over HTTP; needs a clock or server state; unsupported for a given system). Includes the deferred injection variants (homoglyphs, nested JSON, faux system messages, indirect URLs) as inert text. Gold stays evaluator-side.
  - **Proof:** INTEGRATION; BG-FIXTURE, BG-GOLD, BG-SECURITY; every mutation has a gold expectation, a failure metric and a class; a mutated fixture differs from its base in exactly the declared way; no gold or mutation name appears in any arm-visible file.
  - **Evidence:** E-B07-002; 19 mutations and 7 invariants with gold on the real fixture.

<a id="b07-t07-02"></a>

- [x] **B07-T07.02 — Mutation application for each system**
  - **Files:** `palladion-benchmark/benchmark/mutations_apply.py`, `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/benchmark/adapters/common.py`, `palladion-benchmark/tests/test_mutations_apply.py`.
  - **Depends:** B07-T07.01, B07-T04.01, B07-T00.03.
  - **Change:** Apply each mutation to a system's state through the interface that system has (Palladion's upload, approve, revoke and admin routes; the retriever arms' own index rebuild) and record, per mutation and system, whether it was applied or is NOT_RUN or FEATURE_NOT_SUPPORTED with the reason (for example M07 and M15 need the graph, which is off; M08 and M11 need server state no interface sets).
  - **Proof:** INTEGRATION; BG-FIXTURE, BG-SECURITY; a mutation that cannot be applied is a recorded result, never a pass; a mutated Palladion state differs from its base only by the declared patch; an unauthorized read of a revoked passage is counted.
  - **Evidence:** E-B07-002; applied to a rebuild arm and to a real Palladion; unsupported is recorded.

<a id="b07-t08-01"></a>

- [x] **B07-T08.01 — Track C runner**
  - **Files:** `palladion-benchmark/benchmark/track_c.py`, `palladion-benchmark/benchmark/scripted_provider.py`, `palladion-benchmark/scripts/run_track_c.py`, `palladion-benchmark/scripts/comparators.py`, `palladion-benchmark/tests/test_track_c.py`.
  - **Depends:** B07-T01.01, B07-T02.01, B07-T03.01, B07-T04.01, B07-T05.02, B07-T05.03, B07-T06.01, B07-T06.02, B07-T07.02.
  - **Change:** Run E0 to E4 under matched call, tool, token and time budgets, then as native best-effort with disclosed differences. Per-case reset; no state reset inside an episode; one provisioned principal and case per independent episode so no private memory crosses episodes (BADR-0039); memory baselines (none, last N turns, rolling summary, scoped episodic) at an equal context budget for the arms without memory, Palladion's own settings for its arms; cold, warm and hot conditions as far as each arm supports them. The oracle policy-tool condition is NOT_RUN with its reason (BADR-0039).
  - **Proof:** SMOKE; BG-TRACKC; a fact stated in one episode is absent from the next; unavailable arms and unsupported conditions are reported with a reason; counts equal the counting proxy's book.
  - **Evidence:** E-B07-002; runner and entry point smoked end to end with a scripted provider.

<a id="b07-t09-01"></a>

- [x] **B07-T09.01 — Track C pilot measurement**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B07-T08.01, B07-T07.02, B07-T05.01, B07-T05.02, B07-T05.03, B07-T06.01, B07-T06.02, OQ14.
  - **Change:** A small pilot of E0, E1, E3 and E4 (about 8 questions, at least 4 of them mutation cases, and 2 episodes of 4 turns) with real-provider generation under limits the owner states for the run, spread over days as the free quota requires, with the dry-run token estimate shown beside the measured one. Failed, partial and quota-blocked runs are results.
  - **Proof:** MEASUREMENT; BG-TRACKC; budgets, failures and cost recorded; calls never exceed the owner's cap; no confirmatory claim.
  - **Evidence:** E-B07-003; closed with limits by the owner (BADR-0042): E3 answered 3 of 8 turns, E4 NOT_RUN (quota), E0 and E1 not live; no claim.

### Atomic tasks — B08

<a id="b08-t01-01"></a>

- [ ] **B08-T01.01 — M-tier generation**
  - **Files:** `palladion-benchmark/scripts/generate_data.py`, `palladion-benchmark/configs/fixtures.yaml`.
  - **Depends:** B07-T07.01, B02-T07.02, B05-T07.01.
  - **Change:** Generate 12,000 documents, 1,000 single-turn questions and 100 episodes with actual composition reports.
  - **Proof:** SMOKE; BG-FIXTURE, BG-GOLD; actual document mix, language shares and partition counts are reported from the output; 10, 30 and 60 questions per stratum for smoke, dev and test are verified by count; human-authored question variants are added to the audit sample (OQ08).
  - **Evidence:** Not yet executed.

<a id="b08-t01-02"></a>

- [ ] **B08-T01.02 — Gated LLM paraphrase with semantic-equivalence check**
  - **Files:** `palladion-benchmark/benchmark/fixtures/documents.py`, `palladion-benchmark/benchmark/fixtures/validation.py`.
  - **Depends:** B08-T01.01, BADR-0009.
  - **Change:** Optional rewriting through the shared generator accepted only when IDs, dates, thresholds and negations are unchanged.
  - **Proof:** UNIT; BG-FIXTURE; a paraphrase that drops a negation is rejected; rejected rewrites keep the template text.
  - **Evidence:** Not yet executed.

<a id="b08-t02-01"></a>

- [ ] **B08-T02.01 — Development-stage tuning on dev questions only**
  - **Files:** `palladion-benchmark/configs/benchmark.yaml`, `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/configs/evaluation.yaml`.
  - **Depends:** B04-T05.01, B05-T06.01, B06-T06.01, B07-T09.01, B08-T01.01, B08-T01.02, B08-T08.01.
  - **Change:** Tune K, candidate pools, reranker cutoff, graph depth, critic activation and thresholds one lever at a time using a held-out calibration split for confidence work; log every trial; never read test results; define per-arm eligibility in comparators.yaml.
  - **Proof:** MEASUREMENT; BG-PREREG; each configuration change cites a dev result; access to locked-test annotations is not used.
  - **Evidence:** Not yet executed.

<a id="b08-t02-02"></a>

- [ ] **B08-T02.02 — Power simulation and security-suite sizing**
  - **Files:** `palladion-benchmark/benchmark/eval/statistics.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B08-T02.01, B03-T04.01, B08-T01.02.
  - **Change:** Estimate disagreement and cluster correlation from pilot and dev only; simulate paired power; size the targeted security suite from the zero-failure bound.
  - **Proof:** MEASUREMENT; BG-STATS; locked-test data is not read; underpowered endpoints are declared.
  - **Evidence:** Not yet executed.

<a id="b08-t02-03"></a>

- [ ] **B08-T02.03 — Targeted security suite**
  - **Files:** `palladion-benchmark/benchmark/fixtures/questions.py`, `palladion-benchmark/configs/fixtures.yaml`.
  - **Depends:** B08-T02.02, B07-T07.01.
  - **Change:** Generate the dedicated tenant, role, injection and authority-spoof suite at the size B08-T02.02 derives from the zero-failure bound, partitioned by family and sealed with the other test material.
  - **Proof:** UNIT; BG-SECURITY, BG-GOLD; suite size follows the recorded bound; a planted leak in a stub arm is counted.
  - **Evidence:** Not yet executed.

<a id="b08-t03-01"></a>

- [ ] **B08-T03.01 — Preregistration and seal**
  - **Files:** `palladion-benchmark/docs/development/RESEARCH_PROTOCOL.md`, `palladion-benchmark/configs/evaluation.yaml`, `palladion-benchmark/docs/reproducibility.md`.
  - **Depends:** B08-T02.03, OQ10, OQ13.
  - **Change:** Complete the protocol checklist, freeze methods, code, prompts, the ablation list with its base treatments, minimum meaningful effects and the calibration plan, seal test manifests with SHA-256, lock primary pairings, equivalence margin and multiplicity procedure. Before the seal the owner either relabels the 30-item pilot packet or accepts the delegated reading in writing, and the synthesis golds are corrected at the generator (BADR-0026, BR29).
  - **Proof:** DOC; BG-PREREG; sealed hashes verify; an edit after sealing is detected and flags later results exploratory.
  - **Evidence:** Not yet executed.

<a id="b08-t04-01"></a>

- [ ] **B08-T04.01 — Confirmatory run**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B08-T03.01.
  - **Change:** Run all eligible arms on the sealed 600 test questions and 100 episodes in both the common-chunk and native-ingestion tracks; at least three repetitions of the stochastic subset; no selective reruns.
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-TRACKB, BG-TRACKC; initial and post-retry outcomes both reported; every failure preserved.
  - **Evidence:** Not yet executed.

<a id="b08-t05-01"></a>

- [ ] **B08-T05.01 — Ablations and factorial interactions**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/configs/comparators.yaml`.
  - **Depends:** B08-T04.01, B08-T08.01.
  - **Change:** Run the preregistered A01-A16 and declared factorials, labeling A09 and A14 as system ablations and A15 as fixtures-only; any ablation Palladion cannot express without code changes is FEATURE_NOT_SUPPORTED, and ablations not in the sealed list are exploratory. Palladion exposes graph hop depth and counter-search limits but no switch for the critic, gate, preflight, authority check, parser or temporal resolver today.
  - **Proof:** MEASUREMENT; BG-ABLATION; each ablation removes exactly one component against a stated base; interactions reported.
  - **Evidence:** Not yet executed.

<a id="b08-t06-01"></a>

- [ ] **B08-T06.01 — Plots and report generation**
  - **Files:** `palladion-benchmark/benchmark/analysis/plots.py`, `palladion-benchmark/benchmark/analysis/reports.py`.
  - **Depends:** B03-T06.01, B08-T08.10.
  - **Change:** Risk-coverage, quality-cost Pareto and per-stratum figures; versioned Markdown or HTML reports with sections for negative findings and fairness deviations.
  - **Proof:** UNIT; BG-REPORT; dominated arms are marked from data; no single composite is presented as the winner.
  - **Evidence:** Not yet executed.

<a id="b08-t07-01"></a>

- [ ] **B08-T07.01 — Final audit and publication package**
  - **Files:** `palladion-benchmark/docs/reproducibility.md`, `palladion-benchmark/docs/dataset_card.md`, `palladion-benchmark/README.md`.
  - **Depends:** B08-T05.01, B08-T06.01, B08-T08.06, OQ09.
  - **Change:** Error attribution, developer-effort observations (first-build hours, adapter count, setup failures, tuning time per arm), final reproducibility checklist, dataset card and README; a reader can reconstruct a run from its manifest.
  - **Proof:** DOC; BG-REPRO, BG-REPORT; independent end review; claims limited to measured strata.
  - **Evidence:** Not yet executed.

<a id="b08-t08-01"></a>

- [x] **B08-T08.01 — Re-pin Palladion and re-run the gates**
  - **Files:** `palladion-benchmark/configs/comparators.yaml`, `palladion-benchmark/scripts/palladion_runtime.py`, `palladion-benchmark/tests/test_config_loader.py`, `palladion-benchmark/tests/test_palladion_runtime.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B07-T09.01, BADR-0044.
  - **Change:** Move the Palladion pin from `eec4ba5` to `dd70c0e` in all three places it lives (`PINNED_COMMIT`, the YAML pins, the config test), add a test that the YAML pin equals `PINNED_COMMIT`, rebuild the isolated worktree and runtime, re-evaluate the PF02 and PF05 workarounds recorded in B07-T00.04 for the new pin, and check the launcher's `--key-env` path after the key-handling fix.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-REPRO; the benchmark suite and the real-runtime tests pass at the new pin, with Palladion tests skipped at that commit counted as NOT_RUN, not passed; a planted mismatch between the YAML pin and `PINNED_COMMIT` fails the new test.
  - **Evidence:** E-B08-002 (pin dd70c0e; gates pass; Palladion's 33 skipped tests are NOT_RUN).

<a id="b08-t08-07"></a>

- [x] **B08-T08.07 — Daily-limit refusals are QUOTA_BLOCKED, resumable and never a zero**
  - **Files:** `palladion-benchmark/benchmark/generator.py`, `palladion-benchmark/benchmark/runner.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/benchmark/results_check.py`, `palladion-benchmark/tests/test_generator_pool.py`, `palladion-benchmark/tests/test_runner.py`, `palladion-benchmark/tests/test_validate_results.py`.
  - **Depends:** B08-T08.01, BADR-0044.
  - **Change:** A provider refusal whose quota window is a day becomes a `QUOTA_BLOCKED` call outcome (NOT_RUN kind, harness-attributed): the pair is not finalised, the run stops starting new provider calls, and resuming the same run directory on a later day attempts the pending pairs again with both attempts kept in the ledger; the validator and the scorer count quota-blocked pairs apart from arm failures and from zeros. Per-minute refusals keep their handling.
  - **Proof:** UNIT; BG-HARNESS, BG-TRACKB; a scripted provider that refuses with a daily window leaves pairs pending, a resumed run completes them and the ledger shows both attempts; a per-minute refusal is unchanged; no INVALID_RUN is caused by a daily limit; a validator run on a directory with a hole that is not quota-blocked still fails.
  - **Evidence:** E-B08-003 (QUOTA_BLOCKED, resumable; 219 tests pass).

<a id="b08-t08-08"></a>

- [x] **B08-T08.08 — R7a identity, evaluation time and in-pool access filter**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/scripts/palladion_runtime.py`, `palladion-benchmark/tests/test_palladion_adapter.py`, `palladion-benchmark/tests/test_palladion_runtime.py`.
  - **Depends:** B08-T08.01.
  - **Change:** Provision one Palladion reader per benchmark principal through the scoped-admin routes (PF05), upload each restricted document with the readers the neutral rule allows so Palladion's own access list works before ranking, send the case's evaluation time as `as_of` (PF01), stop masking Palladion's output and count any returned document the neutral rule would refuse as `acl_leaked`, and read the lists back with a positive control (BADR-0044 addendum); anything that still cannot be made equal is recorded as a capability difference.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; against the real isolated Palladion, two principals of different tenants see different results for one query, a document is returned inside its validity window at the case's evaluation time and not after it, and a planted empty access list fails the test; the adapter's request body contains `as_of`.
  - **Evidence:** E-B08-004 (native access list, as_of, verify_acl; real-server test; mutant killed).

<a id="b08-t08-09"></a>

- [ ] **B08-T08.09 — Plan digest, cross-run guard, quota ledger and frozen matched lists**
  - **Files:** `palladion-benchmark/benchmark/quota.py`, `palladion-benchmark/benchmark/runner.py`, `palladion-benchmark/benchmark/results_check.py`, `palladion-benchmark/tests/test_quota.py`, `palladion-benchmark/tests/test_runner.py`.
  - **Depends:** B08-T08.07, B08-T08.08.
  - **Change:** The plan digest includes the system-under-test commit, K, evidence budget, condition and model assignment; the validator and the report refuse to pool runs that differ in any of them; a per-model, per-provider-day token ledger is read from the counting proxies' books and gives the day's remaining quota and the planned days; the matched question and episode lists are frozen into a file with its digest before the first spend and recorded in every manifest.
  - **Proof:** UNIT; BG-REPRO, BG-FAIR; runs that differ in pin, K, budget, condition or model are refused, and an identical pair is accepted; the ledger recomputes a day's spend from saved rows and flags a book that disagrees with its totals; editing a frozen list changes its digest and is refused at run time.
  - **Evidence:** Not yet executed.

<a id="b08-t08-10"></a>

- [ ] **B08-T08.10 — Paired statistics across runs and harm metrics over every eligible pair**
  - **Files:** `palladion-benchmark/benchmark/eval/score_run.py`, `palladion-benchmark/benchmark/analysis/tables.py`, `palladion-benchmark/scripts/score_track_a.py`, `palladion-benchmark/scripts/score_track_b.py`, `palladion-benchmark/tests/test_score_run.py`, `palladion-benchmark/tests/test_tables.py`.
  - **Depends:** B08-T08.09, B04-T05.01.
  - **Change:** Score two or more run directories that passed the cross-run guard as paired arms on the same question ids, with the primary pairing R7a against R3 (and E4 against E3 for Track C), exact McNemar and clustered bootstrap intervals, Holm across the exploratory pairs, strata with too few clusters marked descriptive; harm metrics get an all-eligible-pairs value with a "not completed" count beside the conditional rate.
  - **Proof:** UNIT; BG-STATS, BG-METRIC, BG-REPORT; hand-computed pairs match, a quota-blocked pair is neither a harm nor a zero, a pair from a different pin is refused, perfect, empty and shuffled arms separate.
  - **Evidence:** Not yet executed.

<a id="b08-t08-02"></a>

- [ ] **B08-T08.02 — Track A comparison on the S tier (no model, no quota)**
  - **Files:** `palladion-benchmark/scripts/run_track_a.py`, `palladion-benchmark/scripts/score_track_a.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B08-T08.10, B04-T05.01, B06-T05.01.
  - **Change:** Run R0 to R3 and R7a (R7b is FEATURE_NOT_SUPPORTED, E2 NOT_RUN) over the 97 scoreable questions of the S tier under C1 and C2, one arm at a time in separate run directories at K 10 and the 4,000-word budget, then score them as paired arms; withdrawn questions are listed; the 10 native-only questions are excluded and the list is stated.
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-FAIR; every pair is accounted for; the validator passes; the cross-run guard accepts the set; R7a's removed-candidate counts and capability differences are reported; results at earlier pins are not pooled.
  - **Evidence:** Not yet executed.

<a id="b08-t08-03"></a>

- [ ] **B08-T08.03 — Track B comparison on a frozen matched list over several days**
  - **Files:** `palladion-benchmark/scripts/run_track_b.py`, `palladion-benchmark/scripts/score_track_b.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B08-T08.02, B05-T06.01.
  - **Change:** Freeze a seeded, stratum-balanced list of 40 of the 87 eligible questions, assign each question one approved model before the first call, and run R0 to R3 and R7a on it under C2 at K 10 and the 4,000-word budget with one completion cap of 2,000, no failover, a pace read from the provider's headers, and the daily caps of BADR-0044; each day resumes the same run directory; a quota-blocked pair is retried on a later day.
  - **Proof:** MEASUREMENT; BG-TRACKB, BG-FAIR; every question is answered by the same model in every arm; per-day spend and quota-blocked counts are reported; intention-to-treat and conditional tables side by side; no INVALID_RUN is caused by a daily limit; no key appears in any output.
  - **Evidence:** Not yet executed.

<a id="b08-t08-04"></a>

- [ ] **B08-T08.04 — Track C comparison of E0, E1, E3 and E4 on a frozen episode list**
  - **Files:** `palladion-benchmark/scripts/run_track_c.py`, `palladion-benchmark/benchmark/track_c.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B08-T08.09, B07-T09.01.
  - **Change:** Freeze 2 episodes and the cases M01, M13, M14, then run E3 and E4 (each on a freshly prepared runtime, one arm per invocation) and E0 and E1 on the same episodes with qwen as the one model, spreading the quota over days; E0 and E1 mutation cases are NOT_RUN and their live-status turns are a capability difference; E2 stays NOT_RUN.
  - **Proof:** MEASUREMENT; BG-TRACKC, BG-ADAPTER; counts come from the proxy books and agree with the saved rows (`check_books`); NOT_OBSERVABLE is never shown as zero; an episode that cannot finish is reported with the turns done.
  - **Evidence:** Not yet executed.

<a id="b08-t08-05"></a>

- [ ] **B08-T08.05 — Graph comparators: R6 cold, then R4 and R5 with leftover quota**
  - **Files:** `palladion-benchmark/scripts/run_graph_arms.py`, `palladion-benchmark/scripts/comparators.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B08-T08.02, B08-T08.09, B06-T06.01.
  - **Change:** Restart R6 from an empty index on qwen under the limits of BADR-0032 to BADR-0036 and resume it across days until it answers the matched queries or the horizon ends, then R4 and R5 with whatever quota is left after Tracks B and C; run R0 to R3 and R7a on the same 60-document subset so the graph table has matched rivals; an index that does not finish is reported with chunks done and spend.
  - **Proof:** MEASUREMENT; BG-ADAPTER, BG-TRACKA; the proxy stops at the daily limit and records it; a partial index is named as such; graph results are in their own table with the corpus named and never pooled with the full-S results.
  - **Evidence:** Not yet executed.

<a id="b08-t08-06"></a>

- [ ] **B08-T08.06 — Descriptive comparison report with the cost axis**
  - **Files:** `palladion-benchmark/benchmark/analysis/reports.py`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B08-T08.02, B08-T08.03, B08-T08.04, B08-T08.05, B08-T06.01.
  - **Change:** One report of Palladion beside the other systems per stratum and per track: quality measures with intervals, calls, tokens and latency from the proxy books, offline build cost apart from query cost, run states (quota-blocked, NOT_RUN, unsupported) beside scores, each system's coverage of the frozen lists, fairness deviations and capability differences, the limits in force, and the statement that every generative result is a single run; marked exploratory with the reasons (no seal, delegated labels, free tier, 97 questions).
  - **Proof:** MEASUREMENT; BG-REPORT; every figure traces to a run directory and its manifest; no composite winner; dominated systems are marked from data; unmeasured cells say NOT_RUN or NOT_OBSERVABLE; a report refuses runs from different pins.
  - **Evidence:** Not yet executed.

### Atomic tasks — B09

<a id="b09-t01-01"></a>

- [ ] **B09-T01.01 — L-tier stress corpus and concurrency runs**
  - **Files:** `palladion-benchmark/scripts/generate_data.py`, `palladion-benchmark/configs/fixtures.yaml`.
  - **Depends:** B08-T07.01.
  - **Change:** Add decoy mass to reach 60,000 documents without changing gold; run 1/4/16/32 concurrent clients.
  - **Proof:** MEASUREMENT; BG-TRACKA; decoys create no new correct answers; capacity limits disclosed.
  - **Evidence:** Not yet executed.

<a id="b09-t02-01"></a>

- [ ] **B09-T02.01 — Robustness replication**
  - **Files:** `palladion-benchmark/configs/benchmark.yaml`, `palladion-benchmark/scripts/run_track_b.py`.
  - **Depends:** B08-T07.01.
  - **Change:** Repeat the confirmatory protocol with another generator family from the approved pool, another seed and held-out organization templates, as replication only.
  - **Proof:** MEASUREMENT; BG-TRACKB; no tuning on replication results.
  - **Evidence:** Not yet executed.

<a id="b09-t03-01"></a>

- [ ] **B09-T03.01 — External validation datasets**
  - **Files:** `palladion-benchmark/scripts/run_track_a.py`.
  - **Depends:** B08-T07.01.
  - **Change:** Verify availability and licenses of public enterprise benchmarks at run time and evaluate without using their test answers for tuning.
  - **Proof:** MEASUREMENT; BG-TRACKA; unavailable datasets recorded as NOT_RUN.
  - **Evidence:** Not yet executed.
