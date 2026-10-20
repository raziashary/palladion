# Requirements traceability

Current checkpoint 2026-10-20: all 13 P10 cards complete against published feature checkpoint c3c0950 and E-P10-006–008. Source 458 PASS/32 explicit SKIP, installed 91 PASS/2 explicit SKIP, native PDF 1 PASS; additional parser controls pass in overlapping 11-test source/installed runs. Final 70-file package comparison, static/docs gates, current-phase Luna Medium review and owned cleanup pass. 125 of 126 total cards are checked; only P09-T02.07/PF03 performance acceptance remains OPEN. No full historical-document audit or production/semantic efficacy claim is made.

Scope: blueprint v0.2 and user's 2026-10-17 suite request. All system coverage below
records verified P01–P08engineering consumers, with unmeasured research obligations explicit; PROGRESS and the
phase-local EVIDENCE_LOG receipts distinguish verified paths and still-unrun obligations. References use stable heading/section names rather
than fragile line numbers. A row is a coverage obligation, not proof of behavior.

## All blueprint sections

| Source heading | Development obligation | Tasks / proof |
|---|---|---|
| §1 Executive architecture | Locked scope/tools/authority/budgets; test hypotheses rather than assert value | P01-T02, P04-T01–P04-T03; ADR-0003–ADR-0007; G-GATE, G-BUDGET |
| §2 Architecture and trust boundaries | Authenticated entry point, discovery vs canonical ownership, staged stores | P01-T03, P02-T01, P04-T04; G-SOURCE, G-SECURITY |
| §3 Complete runtime flow | Nonexclusive preflight, draft→critic→final gate, bounded failure and persistence | P04-T01–P04-T04, P06-T01–P06-T02; G-BUDGET, G-E2E |
| §4 Ingestion and time-aware authority | Immutable revisions, approvers, exact spans, two temporal axes, reconciliation | P02-T01, P03-T01; G-SOURCE, G-TEMPORAL |
| §5 Hybrid document retrieval | Dense HNSW/BM25 named vectors, one RRF, exact path, contexts, multilingual metrics | P02-T02–P02-T04; G-RETRIEVAL |
| §6 Knowledge graph | Verified identity, provisional links, constraints, bounded source-backed traversal | P07-T01–P07-T03; G-GRAPH |
| §7 Deterministic policy | Approved table discovery/time resolution, safe typed predicates, decision traces | P03-T01–P03-T02; G-TEMPORAL, G-POLICY |
| §8 Live adapters | Named read-only mock gateway, target auth, timestamps/freshness, failure taxonomy | P03-T03; G-LIVE, G-SECURITY |
| §9 Continuity and SQLite memory | Three categories/four scopes, validity vs freshness, generated packet, safe cache | P05-T01–P05-T03; G-MEMORY |
| §10 Critic and answer gate | Structured advisory critique, ledger, claim support, five dispositions, inventory boundary | P04-T03, P06-T01–P06-T03; G-GATE, G-CRITIC |
| §11 Runtime interfaces | Four tools, versioned schemas, budgets/errors/retries/resumability | P01-T02, P04-T01–P04-T04; G-CONTRACT, G-BUDGET |
| §12 Repository responsibility map | Map intended files into existing palladion root, preserve dependency direction | ADR-0001, PROJECT_MAP; P01–P08; source inspection per task |
| §13 Representative code/schemas | Implement missing security/persistence/accounting, not copy sketches blindly | P01-T03, P02-T02, P03-T01–P03-T03, P04-T02–P04-T03; all owning gates |
| §14 Research evaluation | B0–B9, annotated gold, metric denominators, T01–T24, fixed integrity targets | P02-T04, P06-T03, P07-T03, P08-T01–P08-T04; G-RESEARCH |
| §15 Build plan | Preserve Slice 0–7 sequence with consumer-backed exits | P01–P08 in MASTER_DEV_PLAN; phase exits and PROGRESS |
| §16 Security/observability/deployment | Synthetic-only, pin versions, redact trace, limits and fault injection | P01-T01, P03-T03, P04-T04, P08-T03; G-SECURITY, G-E2E |
| §17 Design rules and remaining decisions | Invariants I01–I15 below; answered recommendation directions separated from implementation-time API/measurement evidence | ADR-0012–ADR-0023; RISKS_AND_OPEN_QUESTIONS; owning gates |
| §18 Synthetic walkthrough | Full path with settlement timeout, partial response, cited observation and safe next session | P04-T04, P05-T03, P06-T02; G-E2E |

## Fifteen system invariants

IDs preserve the order of blueprint “System invariants.”

| Invariant | Contract | Tasks | Gate / consumer proof |
|---|---|---|---|
| I01 | Immutable revision and auditable registered status | P01-T03, P02-T01 | G-SOURCE; original-byte citation reader |
| I02 | Derived indexes grant neither authority nor access | P02-T03, P07-T02 | G-SECURITY; no unauthorized model text |
| I03 | Policy scope/time/supersession, never highest score/revision | P03-T01 | G-TEMPORAL; version-selection trace |
| I04 | Missing inputs/incomparable versions are typed incomplete/conflict | P03-T01, P03-T02 | G-POLICY; gate reads decision code |
| I05 | Verified graph identity plus uniqueness protection | P07-T01 | G-GRAPH; concurrent real-store test |
| I06 | Exactly four top-level read tools, no arbitrary network/SQL/action | P04-T01, P03-T03 | G-SECURITY; tool schema and dispatch tests |
| I07 | Deterministic nonexclusive preflight | P04-T01 | G-BUDGET, G-E2E; mixed-tool request |
| I08 | Main ≤5 incl final; critic ≤3; tools/search separately bounded | P04-T02, P06-T01 | G-BUDGET; exception and concurrent attempt accounting |
| I09 | User validity separate from owner-defined live freshness | P05-T01, P03-T03 | G-MEMORY, G-LIVE; stale observation fixture |
| I10 | Packet is context; promotion requires authorization | P05-T01, P05-T02 | G-MEMORY; reader cannot inherit packet grants |
| I11 | Critic cannot certify unsupplied inventory | P06-T03, P08-T02 | G-CRITIC, G-RESEARCH; withheld appendix |
| I12 | Gate checks every material claim; five accurate dispositions | P04-T03 | G-GATE; valid refs plus semantic-support labels |
| I13 | Hypothesis stays explicit and cannot authorize action | P04-T03, P05-T03 | G-GATE; mislabeled directive adversary |
| I14 | Absence claims limited to authorized searched scope | P02-T03, P03-T03, P08-T02 | G-GATE, G-LIVE; not-found vs unavailable |
| I15 | Material graph/critic/fusion/vector changes need reproducible ablation | P06-T03, P07-T03, P08-T02 | G-RESEARCH; raw paired reports including failures |

## Direct user requirements

| Requirement | Owning artifact / acceptance |
|---|---|
| Entire master vision read properly | P00-T01; 18-section map, full-read independent audit and E-DOC-001 |
| Master development plan with every-task reading rules | MASTER_DEV_PLAN; AGENTS entry point |
| ADR, test gates, goal, learning, memory and project map | One canonical development folder; G-DOC and manual review |
| No UI; build system/hypothesis first | ADR-0002; GOAL exclusions and P01–P08 order |
| Later honest comparison under baseline/ | X01 deferred; RESEARCH_PROTOCOL capability/resource tracks |
| All new subagents GPT 6 Luna Medium | ADR-0026 supersedes ADR-0008 effort; scoped dispatch metadata; no silent fallback |
| Dev suite is this task's endpoint | Historical P00 endpoint complete; current explicit P01 GO and phase-local proofs recorded separately |
| Current ADR answers and uv/Groq override | P00-T05; ADR-0011–ADR-0023; real Groq integration replaces only fake-first suggestion, all invariants retained |
| Mandatory phase reviews and explicit implementation GO | AGENTS; MASTER_DEV_PLAN task protocol; pre-phase Luna Medium adversary and one post-phase Luna Medium work auditor; WAIT_FOR_GO |
| Every future adversary/auditor considers the grand vision; publish P00 then wait for P01 | MASTER_DEV_PLAN blueprint review contract: both read full §1–§18, report headings/invariants and phase-local task/consumer/proof coverage; ADR-0011 amendment and E-DOC-004; historical P00 main-push approval is separate from the subsequently given P01 GO |
| Coordinator and subagent inspect all development docs against full vision | P00-T05.04; per-document/whole-blueprint audit evidence in E-DOC-003; structural checker alone insufficient |

The detailed T01–T24 mapping lives once in [TESTING_GATES](TESTING_GATES.md#hard-case-coverage-from-the-blueprint).
Work-package IDs in these coverage tables retain their meaning. Their executable file
owners, dependencies, readers and proof now live in the master's
[atomic register](MASTER_DEV_PLAN.md#atomic-execution-register). Each child proof links
to an exact gate-coverage heading, which links back to its card. Original package/phase
acceptance remains required; child checkboxes do not waive the blueprint invariants.

The follow-up user requirements are P00-T04: atomic file-specific checkbox tasks based
on the requested Arcana reference, plus selected useful development rules tailored to
Palladion AGENTS. ADR-0009/ADR-0010 and E-DOC-002 govern and prove that adaptation.

Current P00-T05 amendments accept every recommendation direction, use editable owner
answers, select uv and real Groq generation and mandate reviews. The only blueprint
build-method override is Slice 3's suggested mock-LLM-first path: real Groq now proves
generative integration. P01/P03 deterministic contracts and policy evaluation still need
no generative call; operational APIs remain read-only mocks. No source/model score creates
authority, no new fifth tool, no unlocked budget or synthetic-data exception is implied.
When requirements change, update task, gate, traceability, ADR/risk and affected source/tests
together. Add IDs; do not silently renumber stable references.

P04 phase-local consumer receipt E-P04-001 now covers runtime preflight→native tool
handler→canonical evidence/policy/live/memory→reserved final→necessary-condition gate→
message/citation/trace readers. Cross-cutting obligations remain split: P05 full memory,
P06 mandatory critic/semantic challenge, P07 graph and P08 scientific scoring. Actual
provider/model and failure history are explicit; P04 end review and resolution are complete; later phase consumers remain deferred.


P05 receipt E-P05-001 extends I09/I10/I13 via explicit owner validity/FTS/team/promotions,
canonical revalidation and packet category producers. Tests exercise correction/expiry/
close/revocation, actual Qdrant cache readers and fresh live follow-up; actual Groq pilot
scores packet versus answer omissions separately and retains0/3 strict completions.
This is phase-local mechanism evidence, not proof of the research hypothesis. P06 critic,
P07 graph, P08 semantic/held-out evaluation and X01 remain explicitly deferred.

P05 phase-local closure: E-P05-001 records allseven atomic tasks, installed49file
artifact,258disjoint automated checks, actual model pilot (including0/3 strict
completions), sole end review and R1/R2 plus third-turn correction resolution. Full research/semantic/critic/graph
obligations remain with their later phases; no broad integrity guarantee inferred.

P06 E-P06-001 extends I08/I11/I12/I15 through structured advisory review, shared bounded
search, canonical revalidation, redacted consumers and frozen paired evidence.
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
At the historical P06 checkpoint, P07 graph/P08 adjudicated research/X01 comparators remained deferred; no P07 GO or P06
main push is inferred. No unanswered P06 owner ADR. Owned processes stopped, storage
preserved and ports16333/16334/18080 verified free; foreign benchmark/editor work untouched.

## Owner amendment: automatic memory promotion in P07

ADR0066 supplements blueprint §9.1/§9.2 and I09/I10 scope/authority controls without editing the vision. P07-T04.01 owns sessions/provenance migration6; T04.02 deterministic chunk classifier; T04.03 cosine/loss supplement; T04.04 automatic write→session packet/recall; T04.05 actual-reader/provider and pilot proof. Semantic means USER-wide preference continuity, not shared organization policy; procedural experience is unapproved tooling/workflow context, distinct from blueprint-approved canonical templates. Both preserve original case/source ACL. Episodic recall is session-local even though canonical case audit/evidence persist. Existing operator-written MemorySpec entries and P05 proof do not establish this new automation.


## P07 final phase-local disposition (2026-10-19)

E-P07-002 records all11cards, actual source/installed/CLI/provider and original-reader proof, the sole GPT6LunaMedium end audit and same-reviewer resolution. The reviewer read the full blueprint (§1–§18), I01–I15, graph and memory amendment; three current-facing document contradictions were fixed and rechecked. No confirmed source defect remained. Graph has0incremental recoveries in4paired queries and stays off by default; controlled path recovery proves integration only. PathA automatic promotion and opt-in bounded local PathB retain original ACL/authorityNONE;4mechanical pilot labels pass,2semantic labels remain unknown. Historical failures and intermediate pending statuses above remain dated snapshots, not current scope. No unanswered P07 owner ADR; P08 adjudication, generalization and external comparisons remain excluded.


## P08 current implementation and proof overlay

P08-T01/02 now bind explicit approved protocol, development/evaluation family splits,
all11arms/44observations, original failures and per-attempt costs. E-P08-002 and
[evaluation report](evidence/P08_RESULTS.md) link raw replay/public hashes and the actual
consumer checks. I01–I15 retain their original authority boundaries: optional treatments
cannot create facts, scope or operational permission. T01–T24 map to executable nodes in
`data/demo/p08_integrity_controls.json`; reconcile.py reports missing/skipped/failed
checks explicitly. Historical reconciliation retains20PASS/4FAIL; current source+actual-injection+serialized
integration reconciliation is24PASS, with exact JUnit hashes in the supplemental receipt.
This is mechanical control coverage, not semantic certification.
Human-adjudicated efficacy, external baselines and production generalization remain
unestablished. Sole phase end audit and same-reviewer resolution are verified at E-P08-003.


## P10 extension traceability

| Owner outcome | Blueprint constraints | Atomic owners | Required consumer proof |
|---|---|---|---|
| PF07 published-text graph setup | §6, I01/I02/I05/I06 | P10-T01.01/02 | Admin HTTP → durable exact proof → canonical graph → actual projection/search → source revalidation |
| Additional text/code/PDF formats | §4.1–4.4/4.6, I01/I02 | P10-T02.01–04 | Original bytes + derived extraction/page proof → approval → search/citation + original readback |
| Broader deterministic memory | §9/§14, owner privateUSER overrideADR0066/0098, I09/I10/I15 | P10-T03.01/02 | Event → versioned classifier → persisted decision/link → scoped recall; synthetic error counts |
| Conversation continuity | §3/§9.2/§16, I06/I08/I09/I10 | P10-T04.01/02 | Own-session original events → bounded revalidated turn projection → automatic packet → actual next-turn model consumer |
| Clear fixtures/public terms | §12/§14/§18 | P10-T05.01/02, P10-T06.01 | Preserved negative controls, source-backed README glossary, single audit and documented limitations |
