# Project goal

As of 2026-10-17 (Asia/Bangkok). Owner: user; coordinator maintains evidence.

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
| O02: Correct policy and live evidence | No policy/live code exists | P03; G-TEMPORAL, G-POLICY, G-LIVE; trusted time/facts plus replayable rule trace |
| O03: Bounded, honestly qualified answers | No agent/gate exists | P04; G-BUDGET, G-GATE, G-SECURITY; actual Groq qwen/qwen3.8-27b message API and canonical citation readback |
| O04: Safe continuity | No runtime memory exists; developer memory is a separate document | P05; G-MEMORY; second authorized request consumes persisted state |
| O05: Measured self-challenge | No critic exists | P06; G-CRITIC; frozen-draft paired evaluation, correction and false-veto rates |
| O06: Tested graph value | No graph exists; optional discovery layer | P07; G-GRAPH; graph-on/off paired evidence and cost; disable if unjustified |
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
P02 package selection and implementation are now explicitly authorized. P01 pins and Python 3.14.7 locked/wheel compatibility
are verified at E-P01-001; embedding/retrieval and provider behavior remain future proof.
The existing app .venv is reused and ignored. Runtime model access needs explicit command enablement,
not merely credentials. User's root `.env` and `.gitignore` are preserved.

Current user instruction explicitly authorizes P02 end-to-end, following completed P00/P01. Both future review roles must read the full blueprint and report traceable coverage.

Excluded now: P03+ implementation, UI, actual payments or mutations, private data,
real enterprise connectors, production signoff, and comparator implementations. Later
system work follows the plan; later external comparisons require their own concrete scope.

## Phase checklist

- [x] P00 — suite, atomic refinement, owner answers, full-vision checks and final reviewer-contract audit/resolution verified (E-DOC-001–E-DOC-004)
- [x] P01 — corpus, contracts, adversarial fixtures (Slice 0); E-P01-001 tests, installed-wheel smoke and single audit/resolution
- [x] P02 — provenance-first retrieval (Slice 1); E-P02-001 all15 tasks, real Qdrant/HTTP/pilot/wheel and audit resolution
- [ ] P03 — temporal policy and mock observations (Slice 2)
- [ ] P04 — bounded runtime and gate (Slice 3)
- [ ] P05 — memory and continuity (Slice 4)
- [ ] P06 — critic experiment (Slice 5)
- [ ] P07 — optional graph experiment (Slice 6)
- [ ] P08 — scientific evaluation and fault injection (Slice 7)
- [ ] X01 — external baseline systems, deferred

Task details/child checkboxes: [master plan](MASTER_DEV_PLAN.md). Phase/gate summaries:
[progress](PROGRESS.md).
