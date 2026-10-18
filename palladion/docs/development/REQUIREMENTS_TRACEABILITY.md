# Requirements traceability

Scope: blueprint v0.2 and user's 2026-10-17 suite request. All system coverage below
mixes verified P01/P02 and planned later consumers; PROGRESS and E-P01-001/E-P02-001
identify phase-local evidence and still-unrun obligations. References use stable heading/section names rather
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
