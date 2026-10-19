# Project goal

Current checkpoint2026-10-19: P06 published6444345; P07 graph and owner-added automatic memory implementation, consumer proof and sole LunaMedium end-review resolution verified (E-P07-001/002). ADR0063–0066 owner approvals preserved. Graph stays off after zero incremental recoveries. P08/UI/benchmark edits and another main push remain excluded. Older phase snapshots below are historical.

As of 2026-10-19 (Asia/Bangkok). Owner: user; coordinator maintains evidence.

## Development-suite outcomes

Create a source-grounded, internally navigable suite that lets a future session implement
and test Palladion without reconstructing the vision or mistaking planned code for built code.

| Outcome | Completion proof | State |
|---|---|---|
| D01: Master plan covers all eight blueprint build slices, sequencing and task reading rules | P00-T01–P00-T03; G-DOC; E-DOC-001 | DONE |
| D02: ADRs, risks, project goal/memory/map/learning and current progress share one folder | P00-T02; G-DOC; independent audit, E-DOC-001 | DONE |
| D03: All 15 invariants and T01–T24 map to planned tasks and falsifiable gates | REQUIREMENTS_TRACEABILITY and TESTING_GATES; G-DOC; audit, E-DOC-001 | DONE |
| D04: Hypothesis protocol preserves negative results and fair deferred comparisons | RESEARCH_PROTOCOL; ADR-0002; audit, E-DOC-001 | DONE |
| D05: Documentation validates; scoped diff reviewed and preserved | G-DOC, E-DOC-001; documentation checkpoint containing this record | DONE |
| D06: Master plan contains atomic file-specific tasks with dependencies, readers and proof; useful Arcana rules tailored into AGENTS | P00-T04; ADR-0009/ADR-0010; G-DOC; E-DOC-002 | DONE |
| D07: Owner answers and uv/Groq choice recorded in editable ADRs; mandatory phase reviews and GO hold applied; coordinator and auditor verify every development document against full vision | P00-T05; ADR-0011–ADR-0023; E-DOC-003 and final E-DOC-004 audit/resolution | DONE |

Documentation completion does not close any system gate or establish the research hypothesis.

## System research objective

Determine whether an evidence-first, bounded agent combining retrieval, deterministic
policies, continuity, critique, and provenance reduces unsupported answers relative to
simpler systems, while reporting its latency, cost, abstention, and usefulness tradeoffs.
A null or adverse result is a valid research outcome.

| Outcome | Scope and baseline | Proof and dependency |
|---|---|---|
| O01: Attributable source discovery | Immutable originals, ingestion, real Qdrant search and citation API exist; P02 audit/resolution verified; synthetic MD/TXT only | P01–P02; G-CONTRACT, G-SOURCE, G-RETRIEVAL; original bytes read through citation API |
| O02: Correct policy and live evidence | P03 domain implementation, validation and audit complete; P04 final-gate integration verified at E-P04-001; broader critic adequacy remains P06 | P03; G-TEMPORAL, G-POLICY, G-LIVE; trusted time/facts plus replayable rule trace |
| O03: Bounded, honestly qualified answers | P04 agent/gate and selected actual Groq consumers exist; phase-local implementation/proof and single audit/resolution complete; model failures retained | P04; G-BUDGET, G-GATE, G-SECURITY; actual explicitly selected Groq three-model message API and canonical citation readback |
| O04: Safe continuity | P05 scoped memory/packet/cache/follow-up consumers and third-turn correction verified with sole audit/resolution; actual pilot failures retained; developer memory is separate | P05; G-MEMORY; second authorized request consumes persisted state |
| O05: Measured self-challenge | Critic/runtime/guards implemented;16actual frozen conditions recorded with failures; default-budget real review/final/readback verified; exact-clause recovery verified; final-source16-condition matrix neutral for full correction; sole end audit resolved;307disjoint checks and final live/installed proofs; no semantic accuracy claim | P06; G-CRITIC; frozen-draft paired evaluation, correction and false-veto rates |
| O06: Tested graph value | Optional canonical source-linked graph implemented; actual paired pilot finds0incremental exception recoveries, graph remains defaultoff. Live worker/API/Groq proof and final phase gates/audit resolution recorded; negative-result disable exit verified | P07; G-GRAPH; graph-on/off paired evidence and cost; disable if unjustified |
| O07: Reproducible conclusion | Retrieval-only pilot recorded; adjudicated/full-answer benchmark and general performance claims remain absent | P08; G-RESEARCH and G-E2E; pinned run manifest, held-out results and failure taxonomy |
| O08: Honest external comparison later | `baseline/` empty; no comparator performance known | X01 deferred; shared evaluation adapter, capability and resource disclosures |

## Acceptance boundaries

The fixed integrity targets from blueprint “Initial acceptance gates” are: 100% of released
verified material claims reference existing currently authorized evidence IDs or approved
rule traces in the harness; zero successful restricted-content leaks in written tests;
zero unapproved operational side effects; all authored temporal fixtures correct; and
correct no-evidence, no-tool, and conflict handling. These targets apply to the test set.
Citation existence alone does not prove semantic support.

Empirical quality/improvement thresholds remain unset until B0/B1 measurements. Freeze
them on development data before the final held-out evaluation, record them in an ADR,
and retain the original failure results if a target is missed.

## Scope, dependencies, and exclusions

System-first modular Python prototype, FastAPI API, SQLite canonical registry and memory,
Qdrant discovery, optional Neo4j, typed JSON policies, mock live adapters, pluggable models.
uv and Groq `qwen/qwen3.8-27b` are selected. Delegated P01 package selection is complete;
P02 package/embedding/retrieval verification is recorded at E-P02-001/002. Python3.14.7 locked/wheel
compatibility is verified; P03 policy/live domain proof is at E-P03-001. Provider behavior remains P04 proof.
The existing app .venv is reused and ignored. Runtime model access needs explicit command enablement,
not merely credentials. User's root `.env` and `.gitignore` are preserved.

Current user instruction explicitly authorizes P07 graph and owner-added automatic memory work. P06 is published at6444345. Both review roles read the full blueprint and report traceable coverage; P07 sole end-review documentation corrections are verified.

Excluded now: P08+ implementation, UI, actual payments or mutations, private data,
real enterprise connectors, production signoff, and comparator implementations. Later
system work follows the plan; later external comparisons require their own concrete scope.

## Phase checklist

- [x] P00 — suite, atomic refinement, owner answers, full-vision checks and final reviewer-contract audit/resolution verified (E-DOC-001–E-DOC-004)
- [x] P01 — corpus, contracts, adversarial fixtures (Slice 0); E-P01-001 tests, installed-wheel smoke and single audit/resolution
- [x] P02 — provenance-first retrieval (Slice 1); E-P02-001 all15 tasks, real Qdrant/HTTP/pilot/wheel and audit resolution
- [x] P03 — temporal policy and mock observations (Slice 2)
- [x] P04 — bounded runtime and gate (Slice 3); E-P04-001, phase-local proof and single audit/resolution
- [x] P05 — memory and continuity (Slice 4); E-P05-001, phase-local proof and single audit/resolution; no H04 success claim
- [x] P06 — critic experiment (Slice 5); E-P06-001/002, all6cards, final consumer proof/audit, neutral pilot retained
- [x] P07 — optional graph experiment and owner-added automatic memory (Slice 6); E-P07-001/002, negative graph exit and sole review resolution
- [ ] P08 — scientific evaluation and fault injection (Slice 7)
- [ ] X01 — external baseline systems, deferred

Task details/child checkboxes: [master plan](MASTER_DEV_PLAN.md). Phase/gate summaries:
[progress](PROGRESS.md).

Owner approved ADR0053 via async reply2026-10-19 (supersedes earlier pending
checkpoint text). Opt-in model-call pacing defaults0 and is now implemented, with
post-wait caller authorization/evidence validation. Focused98checksPASS15.51s;
post-fix recovery/default-budget proofs, sole review resolution, final gates and cleanup are verified.
ADR0054 strengthens pre/post critic discovery attribution and safe attempt diagnostics.

## P07 owner-added automatic memory outcome

O09: backend event persistence automatically produces bounded, attributable memory decisions. PathA deterministic rules is primary; local cosine/loss PathB is fallback/additional evidence with lower influence and cannot override eligibility/ACL/authority. Explicit user preferences persist USER-wide across sessions, with original case/source permissions retained. Procedural tool/workflow experience is unapproved context; remaining chunks are session-local episodic. Explicit backend session start/end and compatible old message clients are implemented. P07-T04.01–05 are verified, including sole end-review resolution. E-P07-002 records v6 preservation/backup/rollback, idempotent chunk links, writer→reopened reader, session/user/revocation negatives, the bounded category/cost/abstention pilot and actual Groq next-turn consumption. No new LLM classifier/tool or organization policy promotion. Semantic accuracy remains unadjudicated.
