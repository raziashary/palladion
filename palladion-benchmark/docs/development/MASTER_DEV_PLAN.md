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
| B04-T01 | R0 and R1 over shared chunks | Exact-ID and semantic probes behave; ANN loss measured |
| B04-T02 | R2 and R3 with C1/C2 and equal token budgets | Budgets equal by counted tokens |
| B04-T03 | R7a Palladion adapter | HTTP only; no import; unavailable is NOT_RUN |
| B04-T04 | Build, Track A runner and result validator | No gold in artifacts; leakage rejected |
| B04-T05 | Pilot measurement | Counts and failures recorded; no superiority claim |

Exit: Track A pilot for R0, R1, R2, R3 and R7a with manual failure inspection. Pilot excluded from held-out claims.

## B05 — Answer-level evaluation and Track B (Slice 2)

Goal O05. Read protocol §3 Track B, §9, §10 and §14.5. Depends on B04 and B01-T05. Owner modules: citations, policy, abstention, judge_audit, run_track_b.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B05-T01 | Citation metrics | Fabrication and uncited claims counted |
| B05-T02 | Temporal and policy scoring | Basis-specific, not recency |
| B05-T03 | Abstention and loss | Always-abstain penalized |
| B05-T04 | Rubric, annotation guide and judge audit | Human or deterministic label cannot be overwritten |
| B05-T05 | Track B runner | Same generator family and budget; pairing rule enforced |
| B05-T06 | Track B pilot | Real provider; failures preserved |

Exit: controlled retrieval-to-answer pilot with a recorded generator pool. No confirmatory claim.

## B06 — Graph and research comparators R4–R7b (Slice 3)

Goal O06. Read protocol §2.1, §3.1 items 8–9, §11.2 and §21. Depends on B04. Cross-project dependency: Palladion graph mode (R7b). Quota constraint OQ06.

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B06-T01 | HippoRAG 2 adapter | Official path, pinned, deviations recorded |
| B06-T02 | GraphRAG Local adapter; Global separate | Modes never merged |
| B06-T03 | LightRAG adapter | Upstream identity verified |
| B06-T04 | Palladion graph mode | Absent feature is NOT_RUN |
| B06-T05 | Graph metrics | Unsupported edges raise false-association |
| B06-T06 | Cold-state run with indexing cost | Indexing and query cost both reported |

Exit: Track A on S tier for the graph arms with full costs, or recorded NOT_RUN reasons.

## B07 — System arms, memory, critic and mutations (Slice 4)

Goal O07. Read protocol §2.2, §5.3–5.4, §11, §16 and §17. Depends on B04, B05 and B02. Cross-project dependency: Palladion message interface and critic (P06 on its plan).

| Task | Work and producer → consumer | Acceptance / proof |
|---|---|---|
| B07-T01 | E0 LangChain two-step | Pinned; budgeted |
| B07-T02 | E1 LangGraph loop | Matched budget |
| B07-T03 | E2 Google ADK, conditional | Without access: NOT_RUN |
| B07-T04 | E3/E4 Palladion system adapter | Actual invocation counts |
| B07-T05 | Episodes, update events, memory and update-consistency metrics | Episode partitions; poisoning counted; stale-index windows measured |
| B07-T06 | Critic and tool-use metrics | Injected-error pairs scored |
| B07-T07 | Mutation and metamorphic fixtures | 19 mutations and 7 invariants with gold |
| B07-T08 | Track C runner | No cross-episode leakage |
| B07-T09 | Track C pilot | Budgets and failures recorded |

Exit: native end-to-end pilot with mutation cases. No confirmatory claim.

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

Exit: sealed, reproducible results with confidence intervals and failures. A null or adverse result is a completed experiment (protocol §19.4).

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

- [ ] **B02-T07.02 — Stratified pilot label audit**
  - **Files:** `palladion-benchmark/benchmark/fixtures/audit.py`, `palladion-benchmark/tests/test_label_audit.py`, `palladion-benchmark/docs/dataset_card.md`, `palladion-benchmark/docs/development/EVIDENCE_LOG.md`.
  - **Depends:** B02-T07.01, OQ08, BADR-0019, BADR-0020.
  - **Change:** Build a blinded, seeded, stratified audit packet (about 30 items); the owner labels it and also checks that the cited clauses exist in the rendered text and suffice; a blinded LLM second pass runs under the BADR-0019 call budget; record agreement with denominators (owner against LLM, not human against human), disagreements, and fix or withdraw defective cases before any measurement.
  - **Proof:** MEASUREMENT; BG-GOLD; agreement statistic with denominators and the non-independence limit stated; defects found and their disposition recorded; every post-audit gold edit logged with hashes; the packet holds no gold field.
  - **Evidence:** Not yet executed.

### Atomic tasks — B03

<a id="b03-t01-01"></a>

- [ ] **B03-T01.01 — Chunk-to-span normalization**
  - **Files:** `palladion-benchmark/benchmark/eval/__init__.py`, `palladion-benchmark/benchmark/eval/normalize.py`, `palladion-benchmark/benchmark/contracts.py`, `palladion-benchmark/tests/test_span_alignment.py`.
  - **Depends:** B02-T04.01, B02-T03.01, B01-T02.01, BADR-0024.
  - **Change:** Add optional source_document_id and source_sha256 to EvidenceCandidate (default none, so existing arms keep working) and a GoldRecord reader that checks the gold digest; map returned chunks to document, clause and offsets by the locator grammar and the folding and containment rules fixed in BADR-0024; report exact identity and overlap separately, with overlap credit never counted in headline metrics; label alignment-only mappings.
  - **Proof:** UNIT; BG-METRIC, BG-ADAPTER; differently chunked identical text aligns; a clause split across two chunks, a chunk spanning two clauses and a re-flowed table map correctly; a stale copy earns overlap credit and no identity credit; a candidate without provenance never receives a native citation; gold read back from disk equals the gold written.
  - **Evidence:** Not yet executed.

<a id="b03-t02-01"></a>

- [ ] **B03-T02.01 — Slot coverage and complete evidence sets**
  - **Files:** `palladion-benchmark/benchmark/eval/evidence_sets.py`, `palladion-benchmark/tests/test_evidence_metrics.py`.
  - **Depends:** B03-T01.01, BADR-0024.
  - **Change:** SlotCoverage@K and CompleteSet@K over the alternative minimal sets of records that have satisfiable slots; records with no satisfiable evidence (unanswerable, blocked, live-unavailable) return not-applicable, never zero or one; relevance is binary slot match (BADR-0024); the unit of evaluation, deduplication and every denominator are defined in evaluation.yaml.
  - **Proof:** UNIT; BG-METRIC; an oracle retriever scores 1, an empty one 0, and seven relevant chunks missing the exception score CompleteSet 0; a partial record and an unanswerable record each behave as defined; a duplicated candidate adds nothing.
  - **Evidence:** Not yet executed.

<a id="b03-t03-01"></a>

- [ ] **B03-T03.01 — Conventional ranking metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/retrieval.py`, `palladion-benchmark/tests/test_retrieval_metrics.py`.
  - **Depends:** B03-T01.01, BADR-0024.
  - **Change:** Precision, recall, MRR, nDCG, MAP and Success at K with binary gain over slot-matched units; short lists, zero relevant units and ideal-DCG zero are defined, not guessed.
  - **Proof:** UNIT; BG-METRIC; hand-computed values match; a shuffled ranking scores below the ideal one; a list shorter than K and a record with no relevant unit follow the written rule.
  - **Evidence:** Not yet executed.

<a id="b03-t03-02"></a>

- [ ] **B03-T03.02 — Provenance-aware retrieval metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/retrieval.py`, `palladion-benchmark/tests/test_retrieval_metrics.py`.
  - **Depends:** B03-T03.01, B03-T02.01, B02-T01.02, B02-T03.01, BADR-0024.
  - **Change:** Valid-source recall, wrong-vintage intrusion (in the family, not applicable, history not allowed), forbidden-source exposure, authority confusion, exception recall, conflicting-pair recall, locator resolution, evidence density and token efficiency (whitespace-word tokens), and entity-disambiguation error where the fixture has the gold; slot kinds come from a name-to-kind table in evaluation.yaml. Noise slope, paraphrase stability and rank sensitivity need inputs no earlier phase produces and move to B07-T07.01, B08-T01.02 and B09-T01.01. The manifest gains the recorded interval and the gold a history-allowed flag so intrusion can be decided.
  - **Proof:** UNIT; BG-METRIC, BG-SECURITY; the planted newer-but-inapplicable version is counted as intrusion even though it ranks first; a live citation is excluded from Track A denominators; every card metric sits in exactly one metric group.
  - **Evidence:** Not yet executed.

<a id="b03-t04-01"></a>

- [ ] **B03-T04.01 — Paired statistics**
  - **Files:** `palladion-benchmark/benchmark/eval/statistics.py`, `palladion-benchmark/tests/test_statistics.py`.
  - **Depends:** B01-T02.02.
  - **Change:** Paired cluster bootstrap with a fixed method, seed and minimum cluster count (below it the interval is labelled descriptive), exact McNemar, Holm over an explicit family argument, TOST equivalence with the margin as an input and a harm-direction flag, the exact zero-failure upper bound computed from n, Brier, log loss, ECE with disclosed bins, and Monte Carlo power simulation. Non-completed pairs enter binary endpoints as failures in the intention-to-treat table and are excluded and counted in the conditional table.
  - **Proof:** UNIT; BG-STATS; a synthetic known effect is recovered; simulated CI coverage is near nominal at the pilot and test cluster counts; clustering widens the interval against the naive one; an arm that times out on hard cases changes the intention-to-treat result and not the conditional one.
  - **Evidence:** Not yet executed.

<a id="b03-t05-01"></a>

- [ ] **B03-T05.01 — Latency and cost accounting**
  - **Files:** `palladion-benchmark/benchmark/eval/cost_latency.py`.
  - **Depends:** B01-T03.03, B01-T04.01.
  - **Change:** p50/p90/p95/p99 by a quantile method fixed in evaluation.yaml, computed over completed calls with timed-out calls counted and reported beside as at least the deadline; online cost from ledger durations and system-reported usage, offline cost from the index record B04 writes, and the amortization formula; marginal-update costs belong to B07-T05.01. Missing values stay missing.
  - **Proof:** UNIT; BG-METRIC; hand-computed quantiles match; null cost is never summed as zero; a TIMEOUT record is not read as an observed latency.
  - **Evidence:** Not yet executed.

<a id="b03-t06-01"></a>

- [ ] **B03-T06.01 — Scorecards and pairwise effect tables**
  - **Files:** `palladion-benchmark/benchmark/analysis/__init__.py`, `palladion-benchmark/benchmark/analysis/tables.py`.
  - **Depends:** B03-T04.01, B03-T02.01, B03-T07.01.
  - **Change:** Stratum-by-arm tables with n, mean, paired difference, interval and severe-failure counts; NOT_RUN, UNSUPPORTED, INVALID_RUN and TIMEOUT listed beside, not inside, accuracy; conditional-on-completion and end-to-end success reported separately over predeclared eligible subsets.
  - **Proof:** UNIT; BG-REPORT; a planted NOT_RUN arm appears as a status, not as a zero score.
  - **Evidence:** Not yet executed.

<a id="b03-t07-01"></a>

- [ ] **B03-T07.01 — Score-run driver and control arms**
  - **Files:** `palladion-benchmark/benchmark/eval/score_run.py`, `palladion-benchmark/tests/test_score_run.py`.
  - **Depends:** B03-T01.01, B03-T02.01, B03-T03.02, B03-T04.01, B03-T05.01, B01-T04.01, B02-T04.01.
  - **Change:** Read a run directory (ledger, immutable manifest, gold) and score it: every ledger record becomes a score or a run state, never a dropped row; a perfect, an empty and a shuffled control arm run through the real Runner with an injected registry that never enters the production registry; per-stratum controls are stated because perfect and empty coincide where no evidence exists.
  - **Proof:** INTEGRATION; BG-METRIC, BG-REPORT; the three controls separate on the strata where evidence exists and are reported as not distinguishable where it does not; a planted ledger hole or a gold digest mismatch stops the scorer.
  - **Evidence:** Not yet executed.

### Atomic tasks — B04

<a id="b04-t01-01"></a>

- [ ] **B04-T01.01 — R0 lexical arm over the shared chunks**
  - **Files:** `palladion-benchmark/benchmark/adapters/bm25.py`.
  - **Depends:** B03-T01.01, B02-T03.01, B01-T03.01.
  - **Change:** Shared parser, chunk boundaries and metadata; build_index, retrieve and index_stats; declared capabilities.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKA; an exact error-code query ranks its clause first; unsupported ACL filtering is declared, not faked.
  - **Evidence:** Not yet executed.

<a id="b04-t01-02"></a>

- [ ] **B04-T01.02 — R1 dense arm and approximate-vs-exact check**
  - **Files:** `palladion-benchmark/benchmark/adapters/dense.py`.
  - **Depends:** B04-T01.01, OQ04.
  - **Change:** Pinned embedding model and HNSW index; periodic exact k-NN comparison on a representative subset.
  - **Proof:** INTEGRATION; BG-ADAPTER; ANN recall against exact search is measured and recorded; embedding revision is pinned.
  - **Evidence:** Not yet executed.

<a id="b04-t02-01"></a>

- [ ] **B04-T02.01 — R2 hybrid fusion and the two metadata conditions**
  - **Files:** `palladion-benchmark/benchmark/adapters/hybrid.py`.
  - **Depends:** B04-T01.02.
  - **Change:** R0+R1 reciprocal-rank fusion with a pinned constant, exact-key channel reported separately, and C1 text-only versus C2 evidence-governed wrappers.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; C1 and C2 differ only in the declared metadata; the fusion constant appears in the manifest.
  - **Evidence:** Not yet executed.

<a id="b04-t02-02"></a>

- [ ] **B04-T02.02 — R3 reranker arm and token-budget enforcement**
  - **Files:** `palladion-benchmark/benchmark/adapters/hybrid.py`.
  - **Depends:** B04-T02.01, OQ05.
  - **Change:** Pinned cross-encoder over R2 candidates; enforce the 4k and 8k evidence token budgets by counted tokens.
  - **Proof:** INTEGRATION; BG-FAIR; two arms at the same budget deliver within tolerance of the same counted tokens; an over-budget bundle is truncated and flagged.
  - **Evidence:** Not yet executed.

<a id="b04-t03-01"></a>

- [ ] **B04-T03.01 — R7a Palladion retrieval adapter over its HTTP API**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`.
  - **Depends:** B01-T03.01, OQ03.
  - **Change:** Authenticated calls to Palladion's search interface with the principal injected by the harness and an explicit principal-to-case mapping; no import of Palladion code. Pin search mode and graph hop setting in comparators.yaml and read them back into the manifest. Palladion's search takes only case, query, mode and a limit of at most 12 and no clock or token budget, so the adapter truncates by counted tokens on the harness side, marks K=20 and any frozen-clock requirement it cannot honor as NOT_RUN or FEATURE_NOT_SUPPORTED, and declares these as capability differences.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-SECURITY, BG-FAIR; a static scan finds no palladion package import; a real call returns candidates; a K=20 request is flagged, not silently capped; Palladion unavailable is NOT_RUN, never a zero score.
  - **Evidence:** Not yet executed.

<a id="b04-t03-02"></a>

- [ ] **B04-T03.02 — Load the published corpus into Palladion through its authenticated source interface**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`.
  - **Depends:** B04-T03.01, B02-T03.01.
  - **Change:** Upload each published document as the fixture's uploader and approve it as an independent approver through Palladion's source and approval endpoints, mirroring the fixture registry's states; wire per-case live observations to the benchmark mock where Palladion's interface allows, otherwise declare the gap.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; read back counts and hashes against the corpus manifest; a draft is never approved; a mismatch fails the load.
  - **Evidence:** Not yet executed.

<a id="b04-t04-01"></a>

- [ ] **B04-T04.01 — Index build entry point**
  - **Files:** `palladion-benchmark/scripts/build_indices.py`, `palladion-benchmark/scripts/qdrant_server.py`, `palladion-benchmark/tests/test_qdrant_launcher.py`.
  - **Depends:** B04-T02.02, B04-T03.01, BADR-0017.
  - **Change:** Docker-free Qdrant launcher: a checksum-pinned official standalone release run under WSL on 127.0.0.1:17333 with its own data directory, never touching Palladion's store (own implementation of the same method). Build per-arm indexes for a snapshot in two modes, common-chunk (shared parser and boundaries) and native-ingestion (each system parses the originals with its defaults); record time, size, tokens, extraction failures and lost tables.
  - **Proof:** SMOKE; BG-REPRO; rebuild from the same manifest yields matching counts; a failed build is recorded rather than skipped.
  - **Evidence:** Not yet executed.

<a id="b04-t04-02"></a>

- [ ] **B04-T04.02 — Track A runner**
  - **Files:** `palladion-benchmark/scripts/run_track_a.py`.
  - **Depends:** B04-T04.01, B01-T04.01, B03-T02.01, B03-T03.02, B03-T05.01.
  - **Change:** Run arms on a split with intention-to-treat accounting and write run artifacts with manifests.
  - **Proof:** SMOKE; BG-TRACKA; the artifacts contain no gold field; arms not run appear with a reason.
  - **Evidence:** Not yet executed.

<a id="b04-t04-03"></a>

- [ ] **B04-T04.03 — Result validation entry point**
  - **Files:** `palladion-benchmark/scripts/validate_results.py`.
  - **Depends:** B04-T04.02.
  - **Change:** Check schema, call and token budgets, leakage and hashes of a run directory.
  - **Proof:** INTEGRATION; BG-REPRO, BG-FAIR; a run directory containing planted gold text or a read of the locked-test namespace is rejected; a clean directory passes.
  - **Evidence:** Not yet executed.

<a id="b04-t05-01"></a>

- [ ] **B04-T05.01 — Track A pilot measurement**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B04-T04.03, B02-T07.02.
  - **Change:** Run R0, R1, R2, R3 and R7a on the pilot (smoke partition only; the S-tier test partition stays unread), inspect failures by hand, and record scores with denominators; pilot results are excluded from held-out claims.
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-METRIC; exact commands, counts and raw failures preserved; no superiority claim.
  - **Evidence:** Not yet executed.

### Atomic tasks — B05

<a id="b05-t01-01"></a>

- [ ] **B05-T01.01 — Citation metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/citations.py`.
  - **Depends:** B03-T01.01, B02-T04.01.
  - **Change:** Validity, accessibility, temporal applicability, entailment hook, completeness, granularity, stability, diversity and fabrication; precision and recall with visible denominators.
  - **Proof:** UNIT; BG-METRIC; a fabricated locator is detected; uncited false claims are counted separately.
  - **Evidence:** Not yet executed.

<a id="b05-t01-02"></a>

- [ ] **B05-T01.02 — Claim-level scoring and unsupported-directive rate**
  - **Files:** `palladion-benchmark/benchmark/eval/citations.py`.
  - **Depends:** B05-T01.01.
  - **Change:** Decompose answers into atomic claims and score correctness against the hidden world at the as-of time, support, completeness, contradiction, action correctness and usefulness; compute the unsupported operational directive rate with an upper bound and correct substantive-answer coverage, the co-primary Track B endpoints. Action correctness uses deterministic gold, not a judge.
  - **Proof:** UNIT; BG-METRIC; a planted unsupported refund directive is counted and a correct supported answer is not; coverage and directive rate are reported together.
  - **Evidence:** Not yet executed.

<a id="b05-t02-01"></a>

- [ ] **B05-T02.01 — Temporal and policy scoring with oracle-tool condition**
  - **Files:** `palladion-benchmark/benchmark/eval/policy.py`.
  - **Depends:** B02-T01.02.
  - **Change:** Version-selection accuracy, as-of completeness, retroactivity, future-policy leakage, wrong-vintage action rate, exact outcome accuracy, missing-input recall and override attempts.
  - **Proof:** UNIT; BG-METRIC, BG-GOLD; every as-of basis is scored from the declared basis, not recency.
  - **Evidence:** Not yet executed.

<a id="b05-t03-01"></a>

- [ ] **B05-T03.01 — Abstention, selective prediction and loss**
  - **Files:** `palladion-benchmark/benchmark/eval/abstention.py`.
  - **Depends:** B03-T04.01.
  - **Change:** False-answer and false-abstention rates, selective risk and coverage, AURC, reason accuracy, partial utility and the weighted loss matrix with sweeps.
  - **Proof:** UNIT; BG-METRIC; an always-abstain system scores poorly on coverage and partial utility; the winner is reported as conditional when weights flip it.
  - **Evidence:** Not yet executed.

<a id="b05-t04-01"></a>

- [ ] **B05-T04.01 — Scoring rubric and annotation guide**
  - **Files:** `palladion-benchmark/docs/scoring_rubric.md`, `palladion-benchmark/docs/annotation_guide.md`.
  - **Depends:** B05-T01.01, B05-T02.01, B05-T03.01.
  - **Change:** Exact labeler rubrics with examples, double-labeling, blinding, adjudication and agreement procedures.
  - **Proof:** DOC; BG-GOLD; each metric has a rubric entry; the owner and a second reviewer can apply it to the pilot.
  - **Evidence:** Not yet executed.

<a id="b05-t04-02"></a>

- [ ] **B05-T04.02 — Blinded labeling workflow and judge audit**
  - **Files:** `palladion-benchmark/benchmark/eval/judge_audit.py`.
  - **Depends:** B05-T04.01, B01-T05.01.
  - **Change:** Blinded sampling for human labels, LLM judge as a secondary check with exposed prompts, a judge family distinct from the generator that produced the answer, at least two judges, and human-judge disagreement reporting.
  - **Proof:** UNIT; BG-METRIC; judge output cannot overwrite a human or deterministic label; disagreement is reported.
  - **Evidence:** Not yet executed.

<a id="b05-t05-01"></a>

- [ ] **B05-T05.01 — Track B runner**
  - **Files:** `palladion-benchmark/scripts/run_track_b.py`.
  - **Depends:** B04-T04.02, B05-T01.02, B05-T02.01, B05-T03.01, B01-T05.02.
  - **Change:** Same generator family, prompt, answer format, evidence budget and runtime gate for every retriever; per-call model recorded; pairing follows the failover policy; questions that assign_models leaves unassigned are recorded NOT_RUN for every arm.
  - **Proof:** SMOKE; BG-TRACKB, BG-FAIR; a pair whose arms ran on different generator models is flagged; no hidden gold at generation time.
  - **Evidence:** Not yet executed.

<a id="b05-t06-01"></a>

- [ ] **B05-T06.01 — Track B pilot measurement with the real provider**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B05-T05.01.
  - **Change:** Bounded pilot over R2, R3 and R7a with the recorded generator pool; record quota, attempts and failures.
  - **Proof:** MEASUREMENT; BG-TRACKB; real-provider responses used; failures and rate-limit events preserved; no confirmatory claim.
  - **Evidence:** Not yet executed.

### Atomic tasks — B06

<a id="b06-t01-01"></a>

- [ ] **B06-T01.01 — R4 HippoRAG 2 adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/hipporag2.py`.
  - **Depends:** B04-T04.01, OQ06.
  - **Change:** Official pipeline at a pinned commit in an isolated environment; record native configuration, deviations and indexing cost.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; the pinned commit is in the manifest; the official retrieval path is used, not a substitute.
  - **Evidence:** Not yet executed.

<a id="b06-t02-01"></a>

- [ ] **B06-T02.01 — R5 GraphRAG Local adapter with separate Global mode**
  - **Files:** `palladion-benchmark/benchmark/adapters/graphrag.py`.
  - **Depends:** B04-T04.01, OQ06.
  - **Change:** Official local query mode pinned and isolated; Global and DRIFT are separate exploratory modes limited to eligible strata.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; Global results are never merged into the R5 row.
  - **Evidence:** Not yet executed.

<a id="b06-t03-01"></a>

- [ ] **B06-T03.01 — R6 LightRAG adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/lightrag.py`.
  - **Depends:** B04-T04.01, OQ06.
  - **Change:** Official hybrid mode at a verified, pinned upstream commit.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; repository identity and commit verified at run time.
  - **Evidence:** Not yet executed.

<a id="b06-t04-01"></a>

- [ ] **B06-T04.01 — R7b bounded graph-expansion mode and Neo4j service**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`, `palladion-benchmark/docker-compose.yml`.
  - **Depends:** B04-T03.02, OQ12.
  - **Change:** Select Palladion's graph-enabled mode when it exists; otherwise declare FEATURE_NOT_SUPPORTED. Neo4j must also run without Docker (OQ12); the compose service is optional.
  - **Proof:** INTEGRATION; BG-ADAPTER; with the feature absent the arm is NOT_RUN with a reason, never a zero.
  - **Evidence:** Not yet executed.

<a id="b06-t05-01"></a>

- [ ] **B06-T05.01 — Graph-specific metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/retrieval.py`.
  - **Depends:** B03-T03.02.
  - **Change:** Relationship precision and recall, typed-traversal correctness, cross-document hop completion, edge provenance validity, wrong-node merge rate, false-association rate, hub pollution and traversal cost per useful slot.
  - **Proof:** UNIT; BG-METRIC; a planted unsupported edge raises the false-association rate.
  - **Evidence:** Not yet executed.

<a id="b06-t06-01"></a>

- [ ] **B06-T06.01 — Cold-state Track A run for graph arms**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B06-T01.01, B06-T02.01, B06-T03.01, B06-T04.01, B06-T05.01.
  - **Change:** Run R4-R7b on the S tier from cold with full indexing time, extraction calls and storage.
  - **Proof:** MEASUREMENT; BG-TRACKA, BG-FAIR; indexing cost reported with query cost; unsupported capabilities listed.
  - **Evidence:** Not yet executed.

### Atomic tasks — B07

<a id="b07-t01-01"></a>

- [ ] **B07-T01.01 — E0 plain LangChain two-step**
  - **Files:** `palladion-benchmark/benchmark/adapters/langchain.py`.
  - **Depends:** B04-T04.02, B01-T05.01.
  - **Change:** Pinned LangChain components and the shared generator; declared as a reference implementation, not one algorithm.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKC; component versions pinned; call budget enforced.
  - **Evidence:** Not yet executed.

<a id="b07-t02-01"></a>

- [ ] **B07-T02.01 — E1 LangGraph bounded agentic loop**
  - **Files:** `palladion-benchmark/benchmark/adapters/langgraph.py`.
  - **Depends:** B07-T01.01.
  - **Change:** Retriever tool and a loop with the same call, tool and time budget as other arms.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-FAIR; exceeding the matched budget is recorded as a failure.
  - **Evidence:** Not yet executed.

<a id="b07-t03-01"></a>

- [ ] **B07-T03.01 — E2 Google ADK with RAG Engine, conditional**
  - **Files:** `palladion-benchmark/benchmark/adapters/google_adk.py`.
  - **Depends:** B07-T01.01, OQ07.
  - **Change:** Adapter that declares NOT_RUN or FEATURE_NOT_SUPPORTED when access, region, billing or filter support is missing.
  - **Proof:** INTEGRATION; BG-ADAPTER; without access the arm reports NOT_RUN with a reason and no score.
  - **Evidence:** Not yet executed.

<a id="b07-t04-01"></a>

- [ ] **B07-T04.01 — E3 and E4 Palladion system adapter**
  - **Files:** `palladion-benchmark/benchmark/adapters/palladion.py`.
  - **Depends:** B04-T03.02, B06-T04.01, OQ11.
  - **Change:** answer, reset_case, report_usage and report_trace over Palladion's message interface. Palladion's current settings cannot disable the critic (minimum one call) and its independent critic is a later Palladion phase, so E3 and E4 are defined only when Palladion exposes a documented switch and critic; otherwise the arm is FEATURE_NOT_SUPPORTED. The benchmark never edits Palladion to obtain a switch.
  - **Proof:** INTEGRATION; BG-ADAPTER, BG-TRACKC; usage reports actual main and critic invocations; with no critic-off switch E3 is FEATURE_NOT_SUPPORTED and E4 is NOT_RUN, never a relabeled E4.
  - **Evidence:** Not yet executed.

<a id="b07-t05-01"></a>

- [ ] **B07-T05.01 — Multi-turn episodes and time-series update events**
  - **Files:** `palladion-benchmark/benchmark/fixtures/questions.py`, `palladion-benchmark/benchmark/fixtures/world.py`.
  - **Depends:** B02-T04.02, B02-T01.03.
  - **Change:** Episode generator with deterministic clock, partition by episode and scripted transitions in questions.py, and 1,000 document events for the update benchmark in world.py; S-tier pilot uses a small subset.
  - **Proof:** UNIT; BG-GOLD; no episode spans two splits; replay is deterministic.
  - **Evidence:** Not yet executed.

<a id="b07-t05-02"></a>

- [ ] **B07-T05.02 — Memory evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/memory.py`.
  - **Depends:** B07-T05.01.
  - **Change:** Identity continuity, context-anchoring error, provenance preservation, reported-fact validity, live freshness, poisoning promotion, cross-case leakage, packet sufficiency and recovery after correction.
  - **Proof:** UNIT; BG-METRIC, BG-SECURITY; a planted promoted user claim is counted.
  - **Evidence:** Not yet executed.

<a id="b07-t05-03"></a>

- [ ] **B07-T05.03 — Update consistency and stale-index exposure metrics**
  - **Files:** `palladion-benchmark/benchmark/eval/cost_latency.py`.
  - **Depends:** B07-T05.01, B03-T05.01.
  - **Change:** Time-to-consistency and stale-index exposure windows after create, amend, withdraw, supersede, ACL revocation and delete events, scored against the as-of rule and committed source state, separately from retrieval correctness.
  - **Proof:** UNIT; BG-METRIC; a planted lagging index yields a nonzero exposure window and a consistent index yields zero.
  - **Evidence:** Not yet executed.

<a id="b07-t06-01"></a>

- [ ] **B07-T06.01 — Critic evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/critic.py`.
  - **Depends:** B05-T01.01.
  - **Change:** Objection precision and recall, repair and regression rates, additional retrievals and cost per net prevented directive; independent-evidence check.
  - **Proof:** UNIT; BG-METRIC; injected-error pairs and clean drafts both scored; agreement alone is not a metric.
  - **Evidence:** Not yet executed.

<a id="b07-t06-02"></a>

- [ ] **B07-T06.02 — Tool-use evaluation**
  - **Files:** `palladion-benchmark/benchmark/eval/tool_use.py`.
  - **Depends:** B01-T03.03.
  - **Change:** Tool selection recall, unnecessary invocation, argument validity, result utilization, discovery reversal, boundedness, failure interpretation and escalation.
  - **Proof:** UNIT; BG-METRIC; over-budget invocations are counted as failures.
  - **Evidence:** Not yet executed.

<a id="b07-t07-01"></a>

- [ ] **B07-T07.01 — Mutation and metamorphic fixtures**
  - **Files:** `palladion-benchmark/benchmark/fixtures/world.py`, `palladion-benchmark/benchmark/fixtures/questions.py`, `palladion-benchmark/benchmark/fixtures/validation.py`, `palladion-benchmark/tests/test_fixture_integrity.py`.
  - **Depends:** B02-T06.01, B07-T05.01.
  - **Change:** Generate the 19 mutation cases and 7 metamorphic invariants with gold expectations.
  - **Proof:** INTEGRATION; BG-FIXTURE, BG-GOLD, BG-SECURITY; every mutation has a gold expectation and a failure metric; a mutated fixture differs from its base in exactly the declared way.
  - **Evidence:** Not yet executed.

<a id="b07-t08-01"></a>

- [ ] **B07-T08.01 — Track C runner**
  - **Files:** `palladion-benchmark/scripts/run_track_c.py`.
  - **Depends:** B07-T01.01, B07-T02.01, B07-T04.01, B07-T05.02, B07-T05.03, B07-T06.01, B07-T06.02.
  - **Change:** Run E0-E4 under matched budgets and again as native best-effort with disclosed differences, with per-case reset, no state reset inside an episode, memory baselines (none, last N turns, rolling summary, scoped episodic) at an equal context budget, and cold, warm and hot-cache conditions.
  - **Proof:** SMOKE; BG-TRACKC; state does not leak across independent episodes; unavailable arms are reported with a reason.
  - **Evidence:** Not yet executed.

<a id="b07-t09-01"></a>

- [ ] **B07-T09.01 — Track C pilot measurement**
  - **Files:** `palladion-benchmark/docs/development/EVIDENCE_LOG.md`, `palladion-benchmark/docs/development/PROGRESS.md`.
  - **Depends:** B07-T08.01, B07-T07.01.
  - **Change:** Pilot run of E0, E1, E3 and E4 on a pilot subset including mutation cases, with real-provider generation.
  - **Proof:** MEASUREMENT; BG-TRACKC; budgets, failures and cost recorded; no confirmatory claim.
  - **Evidence:** Not yet executed.

### Atomic tasks — B08

<a id="b08-t01-01"></a>

- [ ] **B08-T01.01 — M-tier generation**
  - **Files:** `palladion-benchmark/scripts/generate_data.py`, `palladion-benchmark/configs/fixtures.yaml`.
  - **Depends:** B07-T07.01, B02-T07.02.
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
  - **Depends:** B04-T05.01, B05-T06.01, B06-T06.01, B07-T09.01, B08-T01.01, B08-T01.02.
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
  - **Depends:** B08-T02.03, OQ10.
  - **Change:** Complete the protocol checklist, freeze methods, code, prompts, the ablation list with its base treatments, minimum meaningful effects and the calibration plan, seal test manifests with SHA-256, lock primary pairings, equivalence margin and multiplicity procedure.
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
  - **Depends:** B08-T04.01.
  - **Change:** Run the preregistered A01-A16 and declared factorials, labeling A09 and A14 as system ablations and A15 as fixtures-only; any ablation Palladion cannot express without code changes is FEATURE_NOT_SUPPORTED, and ablations not in the sealed list are exploratory. Palladion exposes graph hop depth and counter-search limits but no switch for the critic, gate, preflight, authority check, parser or temporal resolver today.
  - **Proof:** MEASUREMENT; BG-ABLATION; each ablation removes exactly one component against a stated base; interactions reported.
  - **Evidence:** Not yet executed.

<a id="b08-t06-01"></a>

- [ ] **B08-T06.01 — Plots and report generation**
  - **Files:** `palladion-benchmark/benchmark/analysis/plots.py`, `palladion-benchmark/benchmark/analysis/reports.py`.
  - **Depends:** B03-T06.01, B08-T04.01.
  - **Change:** Risk-coverage, quality-cost Pareto and per-stratum figures; versioned Markdown or HTML reports with sections for negative findings and fairness deviations.
  - **Proof:** UNIT; BG-REPORT; dominated arms are marked from data; no single composite is presented as the winner.
  - **Evidence:** Not yet executed.

<a id="b08-t07-01"></a>

- [ ] **B08-T07.01 — Final audit and publication package**
  - **Files:** `palladion-benchmark/docs/reproducibility.md`, `palladion-benchmark/docs/dataset_card.md`, `palladion-benchmark/README.md`.
  - **Depends:** B08-T05.01, B08-T06.01.
  - **Change:** Error attribution, developer-effort observations (first-build hours, adapter count, setup failures, tuning time per arm), final reproducibility checklist, dataset card and README; a reader can reconstruct a run from its manifest.
  - **Proof:** DOC; BG-REPRO, BG-REPORT; independent end review; claims limited to measured strata.
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
