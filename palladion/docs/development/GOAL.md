# Project goal

Current checkpoint 2026-10-30: P11 (evidence-path remediation from the benchmark's findings) is DONE for its cards P11-T01 to P11-T08, including P11-T06.01 (E-P11-005). The work is implemented, reviewed and measured: Palladion's own suite 687 passed and 33 explicitly skipped (gated Qdrant, Neo4j and provider tests, not passed), ruff and mypy clean, planted mutants killed, independent Haiku 5.5 High review rounds resolved (E-P11-003, E-P11-004), the owner's written acceptance that P11 ran without a formal pre-phase adversary (ADR-0113). The benchmark re-measured it at the new commit `caebd53`: a sealed, pre-registered, retrieval-only Track A run on six fresh worlds (E-B08-013 in the benchmark) gives Palladion's retriever the complete set for 0.399 of questions against 0.226 for the tuned strong hybrid-plus-reranker baseline, +0.173 [+0.118, +0.227], above the registered minimum of 0.05, and +0.130 over the same baseline given Palladion's eligibility rule; on the public SciFact set (ordinary search) it is on par (0.780 against 0.770); Track B (answering, 200 pairs, E-B08-015) is descriptive: Palladion's retriever answered 4 of 31 questions correctly against 2 for the strong baseline (not distinguishable) with the cleanest citations. Limits: the labels are the benchmark generator's and unaudited by a human, one generator wrote corpus, questions and labels, Palladion's retrieval repeats its lists for 92 to 95 percent of questions on a fresh load, it is behind on which-version (Q4) and conflict (Q6) questions and finds no access (Q8) or summary (Q10) question. The benchmark's Track C (E3, E4) at this commit is not done (the first E4 attempt is void) and is the benchmark's card B08-T08.04, not a P11 acceptance. P09/PF03 performance acceptance stays open.

Previous checkpoint 2026-10-20: all 13 P10 cards complete against published feature checkpoint c3c0950 and E-P10-006–008. Source 458 PASS/32 explicit SKIP, installed 91 PASS/2 explicit SKIP, native PDF 1 PASS; additional parser controls pass in overlapping 11-test source/installed runs. Final 70-file package comparison, static/docs gates, current-phase Luna Medium review and owned cleanup pass. 125 of 126 total cards are checked; only P09-T02.07/PF03 performance acceptance remains OPEN. No full historical-document audit or production/semantic efficacy claim is made.

As of2026-10-20 (Asia/Bangkok). Owner: user; coordinator maintains evidence.

## Development-suite outcomes

P11 owner-approved outcomes (2026-10-27): search returns the governing evidence (the older version that governed an earlier case time, the defining policy ahead of the tickets that cite it, ranked passages never displaced by context), chunks carry their title, the agent asks for and sees enough, publication fails closed; speed follows measurement. Proof: P11 cards and E-P11-001, then the benchmark at the new commit.

P10 owner-approved outcomes: provenance-backed graph links reach actual search;
verbatim new text formats and bounded PDF originals/extractions reach current citation
readers; deterministic weighted categories preserve hard boundaries; bounded own-session
conversation context reaches the next model request; README terminology/live/automatic
ownership is clear. Source and actual-service receipts are in
[P10 evidence](evidence/P10_CLASSIFICATION_AND_FORMATS.md). Current worker hardening, installed-package verification, the single final review
and cleanup are verified at E-P10-006/007; published checkpoint c3c0950 closes T06 at E-P10-008.
P09/PF03 performance acceptance is a separate open outcome, not waived by P10.

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
| O07: Reproducible conclusion | Owner-approved all11arm pilot completed44observations/16errors; canonical replay/readback, current24controls and sole end-review resolution verified; semantic efficacy and unobserved candidate-stage metrics remain unknown | P08; G-RESEARCH and G-E2E; pinned run manifest, held-out results and failure taxonomy |
| O08: Honest external comparison later | `baseline/` empty; no comparator performance known | X01 deferred; shared evaluation adapter, capability and resource disclosures |

## Acceptance boundaries

The fixed integrity targets from blueprint “Initial acceptance gates” are: 100% of released
verified material claims reference existing currently authorized evidence IDs or approved
rule traces in the harness; zero successful restricted-content leaks in written tests;
zero unapproved operational side effects; all authored temporal fixtures correct; and
correct no-evidence, no-tool, and conflict handling. These targets apply to the test set.
Citation existence alone does not prove semantic support.

Owner-approved pilot thresholds were frozen after B0/B1 development measurements
(ADR0079). Most arms missed the50%exact-quote target; failures remain reported.
Semantic improvement thresholds and claims require independent human adjudication.

## Scope, dependencies, and exclusions

System-first modular Python prototype, FastAPI API, SQLite canonical registry and memory,
Qdrant discovery, optional Neo4j, typed JSON policies, mock live adapters, pluggable models.
uv and Groq `qwen/qwen3.8-27b` are selected. Delegated P01 package selection is complete;
P02 package/embedding/retrieval verification is recorded at E-P02-001/002. Python3.14.7 locked/wheel
compatibility is verified; P03 policy/live domain proof is at E-P03-001. Provider behavior remains P04 proof.
The existing app .venv is reused and ignored. Runtime model access needs explicit command enablement,
not merely credentials. User's root `.env` and `.gitignore` are preserved.

Current user instruction authorizes full P08 scientific evaluation, observability and
fault injection. P07 graph/automatic memory is published atf97471e. Both review roles
read the full blueprint and report traceable coverage; P08 sole end review and same-reviewer resolution are complete.

Excluded now: UI, actual payments or mutations, private data,
real enterprise connectors, production signoff, and comparator implementations. Later
system work follows the plan; later external comparisons require their own concrete scope.
A further push to main requires explicit approval.

## Phase checklist

- [x] P00 — suite, atomic refinement, owner answers, full-vision checks and final reviewer-contract audit/resolution verified (E-DOC-001–E-DOC-004)
- [x] P01 — corpus, contracts, adversarial fixtures (Slice 0); E-P01-001 tests, installed-wheel smoke and single audit/resolution
- [x] P02 — provenance-first retrieval (Slice 1); E-P02-001 all15 tasks, real Qdrant/HTTP/pilot/wheel and audit resolution
- [x] P03 — temporal policy and mock observations (Slice 2)
- [x] P04 — bounded runtime and gate (Slice 3); E-P04-001, phase-local proof and single audit/resolution
- [x] P05 — memory and continuity (Slice 4); E-P05-001, phase-local proof and single audit/resolution; no H04 success claim
- [x] P06 — critic experiment (Slice 5); E-P06-001/002, all6cards, final consumer proof/audit, neutral pilot retained
- [x] P07 — optional graph experiment and owner-added automatic memory (Slice 6); E-P07-001/002, negative graph exit and sole review resolution
- [x] P08 — scientific evaluation and fault injection engineering pilot (Slice 7); E-P08-001–003, owner-approved pilot boundary and sole end-review resolution; hypothesis/semantic accuracy unproven
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

## O10 — Post-completion audit and approved benchmark handoff

Resolve the confirmed normative gate, study deadline/configuration and T01/T12 proof
findings; implement approved PF01–PF06 with measured limitations. Proof lives in P09's
atomic cards and E-P09 receipts. Current status ACTIVE; no broad quality/production
claim follows. Owner permits a scoped verified main push and completion notes only in
the benchmark handoff document; unrelated benchmark/editor work stays outside ownership.


O10 mechanism checkpoint: PF01/02/04/05/06 consumers and confirmed audit defects have
current source/installed proof. Explicit5second cache implementation does not close
PF03: balanced observations show small-case overhead and expiry/cold costs. Owner's
conditional leave-open direction is preserved in P09-T02.07; broader P09 stays ACTIVE.
