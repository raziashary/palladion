# Project goal

As of 2026-10-18. Owner: user; coordinator maintains evidence.

## Benchmark objective

Build a reproducible, fair and falsifiable experiment that answers the protocol's central question:
when documentation is stale, contradictory, incomplete, permission-limited or dispersed, does Palladion
deliver more supportable and appropriately cautious answers than standard and strong hybrid RAG, graph
retrievers and reference framework stacks, and what extra computation, complexity and latency does that
cost? The asset is the gold evidence, authority and temporal world plus a controlled harness, not a
headline score. A null or adverse result is a valid outcome and is reported as such.

This project builds the benchmark only. The system under test (`palladion/`) is developed elsewhere;
its status is read from its own documents and source, never assumed.

## Outcomes

| Outcome | Scope and completion proof | State |
|---|---|---|
| O00: Development suite exists, validates and is independently reviewed | B00; BG-DOC; E-B00-001, E-B00-002, E-B00-003, E-B00-004 | DONE |
| O01: Harness runs paired, bounded, randomized experiments with immutable manifests and a proven generator entry point | B01; BG-HARNESS, BG-REPRO; E-B01-002 to E-B01-006 | DONE |
| O02: Audited synthetic S-tier world, corpus, gold and validation report | B02; BG-FIXTURE, BG-GOLD, BG-SECURITY; E-B02-001 to E-B02-006; BG-GOLD stays PARTIAL (one non-independent label reader, BADR-0026) | DONE |
| O03: Scorers distinguish perfect, empty and shuffled systems and implement the protocol's statistics | B03; BG-METRIC, BG-STATS, BG-REPORT; E-B03-002 to E-B03-004 | DONE |
| O04: Track A pilot for R0, R1, R2, R3 and R7a | B04; BG-ADAPTER, BG-FAIR, BG-TRACKA; E-B04-001 to E-B04-005 (pilot, no ranking claim) | DONE |
| O05: Answer-level scorers and Track B pilot with the recorded generator pool | B05; BG-METRIC, BG-TRACKB; E-B05-001 to E-B05-004 (live pilot blocked) | IN_PROGRESS |
| O06: Graph and research comparators R4–R7b measured with full cost, or recorded NOT_RUN reasons | B06; BG-ADAPTER, BG-TRACKA | PLANNED |
| O07: Native end-to-end systems E0–E4, memory, critic and tool metrics, 19 mutations and 7 invariants | B07; BG-TRACKC, BG-FIXTURE, BG-SECURITY | PLANNED |
| O08: Sealed confirmatory run and ablations with intervals, failures and bounded claims | B08; BG-PREREG, BG-ABLATION, BG-REPORT | PLANNED |
| O09: Replication and stress, labeled as replication | B09 (conditional on owner authorization of budget); BG-TRACKA, BG-TRACKB | DEFERRED |

Completion of the suite or of any phase does not establish the research hypotheses. Task counts are derived
from the checkbox register and are not a measure of experimental readiness.

## Acceptance boundaries

Protocol §13.2 gates are provisional research targets, not measured results, and are revised only before the
test seal (ADR BADR-0012): zero observed cross-tenant leakage in the locked set plus the dedicated security
suite reported with its upper bound; zero source or citation fabrication in high-risk answers; every main
agent run within five invocations and every critic within three; temporal resolver tests all passing;
manifest integrity; critical unsupported operational actions at target zero with an upper bound; correct-answer
coverage not below an agreed minimum relative to the primary challengers R3 and E3; actual latency and cost
reported with no invented service level. Empirical quality thresholds stay unset until pilot and dev data
exist and are then frozen before the sealed run.

## Scope, dependencies and exclusions

Python harness in `palladion-benchmark/`, own uv environment, synthetic fictional data only, Palladion reached
over its HTTP interface, comparators in isolated pinned environments, generator pool of three Groq models
(ADR BADR-0007). The primary challengers are R3 (hybrid plus reranker) and E3 (Palladion without critic).

Excluded: any edit to `palladion/`, UI, real company or customer data, private corpora, production claims,
"best RAG" claims, and any provider call before the owner provisions a key (OQ01). Phases B01–B09 need the
owner's GO; the suite request covers B00 only.

## Phase checklist

- [x] B00 — development suite (E-B00-001 to E-B00-004)
- [x] B01 — harness foundation (E-B01-001 to E-B01-006)
- [x] B02 — synthetic world, S-tier corpus and gold (E-B02-001 to E-B02-006)
- [x] B03 — evaluation core (E-B03-001 to E-B03-004)
- [x] B04 — retrieval arms R0–R3, R7a and Track A pilot (E-B04-001 to E-B04-005)
- [ ] B05 — answer-level evaluation and Track B pilot
- [ ] B06 — graph and research comparators
- [ ] B07 — system arms, memory, critic, mutations and Track C pilot
- [ ] B08 — scale, tuning, preregistration, confirmatory run and ablations
- [ ] B09 — replication and stress, conditional

Task details and child checkboxes: [master plan](MASTER_DEV_PLAN.md). Phase and gate summaries:
[progress](PROGRESS.md).
