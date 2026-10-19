# Current progress

Updated 2026-10-19. Atomic task state lives in the [master plan](MASTER_DEV_PLAN.md);
command observations and review receipts live in the [evidence log](EVIDENCE_LOG.md).

## Current checkpoint

B04 (Track A arms and pilot) is DONE: all fourteen cards are done and proven (E-B04-002 to E-B04-005; the pre-phase adversary is E-B04-001). The pilot ran R0 to R3 and R7a on the smoke split under C2 and C1 (500 of 500 pairs each, 97 questions scored after withdrawing three defective synthesis questions); the observations are in E-B04-005 and support no ranking claim. The shared harness, a Docker-free Qdrant launcher, R0 to R3 with Palladion's pinned models, an isolated Palladion runtime with the HTTP-only R7a adapter, the build, run, score and validate commands all exist; `uv run pytest` passes 981 tests with ruff and strict mypy clean, every planted defect is killed, and two real smokes (R0 to R3 and R7a over the full corpus) pass the validator. They are not the pilot and support no ranking claim.

B03 (evaluation core) is BUILT and audited: all eight cards are done and proven (E-B03-002 to E-B03-004), with the pre-phase adversary in E-B03-001. The scorers cover identity and text alignment, SlotCoverage and CompleteSet, ranking and provenance metrics, paired statistics, latency and cost, scorecards and a score-run driver, and the perfect, empty and shuffled controls run through the real Runner with an injected registry. `uv run pytest` passes 790 tests with ruff and strict mypy clean; every planted defect is killed. B02 is built; its last card, the pilot label audit, was done under delegation (E-B02-006); the S-tier fixture has 1,200 fictional documents and 100 pilot questions.


B01 (harness foundation) is DONE: all eleven cards are built and proven (E-B01-002 to E-B01-004), the pre-phase Haiku 5.5 adversary (E-B01-001) and the post-phase audit with its resolution check (E-B01-005, E-B01-006) are dispositioned. The harness has typed contracts, strict configs, a 15-arm capability registry, an immutable manifest, tracing and
call budgets, a paired runner with intention-to-treat records, a CLI, a secret scanner and a generator pool. `uv run pytest` passes 371 tests, ruff and strict mypy are clean,
and the real entry point reached all three approved Groq models once each. No dataset, retriever, Palladion call or measurement exists. `make` is not installed and Docker cannot run
on this machine (owner, 2026-10-18), so the Makefile and the compose file were checked statically only; Qdrant will run Docker-free under WSL (BADR-0017).

Decisions in force: in-repo uv project (BADR-0001); generator pool qwen/qwen3.8-27b, openai/gpt-oss-120b, openai/gpt-oss-20b with per-question pre-assignment and no automatic switch
(BADR-0007, BADR-0008, BADR-0015); template-first corpus (BADR-0009); Haiku 5.5 reviewers only (BADR-0003); push to main allowed (BADR-0004); benchmark-local `.env` (BADR-0013);
phase plan approved (BADR-0006); dependencies and extra files (BADR-0014); required citation field, subprocess isolation from B04 and pinned system-under-test checkout (BADR-0016); no Docker, Qdrant as a standalone binary under WSL (BADR-0017).
Still open and tracked: OQ03 (read Palladion's interface at B04), OQ09 (license, before B08-T07.01) and OQ10 (pairings, before B08-T03.01); see
[risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## Phase state

| Phase | State | Evidence / next action |
|---|---|---|
| B00 | DONE | E-B00-001 to E-B00-004 |
| B01 | DONE | E-B01-001 to E-B01-006 |
| B02 | DONE | E-B02-001 to E-B02-006; the label audit was made by the coordinator under the owner's delegation (BADR-0026), so BG-GOLD stays PARTIAL |
| B03 | DONE | E-B03-001 to E-B03-004; the metrics are proven against the controls, not yet against any real arm |
| B04 | DONE | E-B04-001 to E-B04-005; the pilot is exploratory, smoke split only |
| B05 | PLANNED | Depends on B04 and B01-T05 |
| B06 | PLANNED | Depends on B04; quota question OQ06 |
| B07 | PLANNED | Depends on B04, B05, B02 |
| B08 | PLANNED | Depends on B04–B07 exits |
| B09 | DEFERRED | Conditional replication and stress |

## Gate state

| Gate | State | Evidence and limits |
|---|---|---|
| BG-DOC | PASS | Checker and self-test in E-B00-001; independent review E-B00-003. Structural plus one model review only |
| BG-HARNESS | PASS | E-B01-002 to E-B01-006: contracts, budgets, generator, ITT runner, CLI and the live entry-point proof (3 of 3 models), audited. Covers the B01 contract only; it does not test any system under test |
| BG-FIXTURE | PARTIAL | E-B02-002, E-B02-003: determinism across processes, referential, contradiction, merge identity, temporal, leakage and realism checks with planted-defect controls on the S tier. The 19 mutations and the M tier remain (B07-T07, B08-T01) |
| BG-GOLD | PARTIAL | E-B02-002, E-B02-005: schema, mapping, slots, family-grouped partitions and gold-support checks pass; the label audit is done but by one non-independent reader (29 of 30 agree with the gold, E-B02-006); the owner's relabel or acceptance is due before the seal |
| BG-METRIC | PARTIAL | E-B03-002, E-B03-003: retrieval, evidence-set, cost and latency metrics with hand-computed cases and controls; answer-level metrics (B05), graph and system metrics (B06, B07) remain |
| BG-STATS | PARTIAL | E-B03-002, E-B03-003: known effect, simulated coverage, clustering, exact tests and bounds; power sizing and preregistered pairings remain (B08) |
| BG-ADAPTER | PARTIAL | Registry and contract tests (E-B01-003); five real adapters with capabilities proven in tests and two real smokes (E-B04-002); B06 and B07 arms remain |
| BG-FAIR | PARTIAL | E-B04-002: one chunker, filter, budget and tie rule for R0 to R3, C1 and C2 differ only in the filter, R7a's differences declared (BR22, BR24, BR27, BR28); equal-budget claims need the pilot |
| BG-TRACKA | PARTIAL | E-B04-002: runner, scorer and validator work on real runs; the pilot ran (E-B04-005); the sealed confirmatory run is B08-T04.01 |
| BG-TRACKB | NOT_RUN | B05 |
| BG-TRACKC | NOT_RUN | B07 |
| BG-SECURITY | PARTIAL | Secret scan, key handling and the arm-visible allowlist (E-B01-002, E-B01-003); tenant and role visibility in the manifest, the barrier scan of the published tree, existence-hiding live reads and inert injection documents (E-B02-002); retriever-side enforcement remains for B04 onward |
| BG-PREREG | NOT_RUN | B08 |
| BG-ABLATION | NOT_RUN | B08 |
| BG-REPRO | PARTIAL | Manifest and ledger digests, deterministic config digests (E-B01-003); same-seed corpus digests across processes (E-B02-002); result validation exists and passes real runs (E-B04-002); the sealed confirmatory run is B08 |
| BG-REPORT | PARTIAL | E-B03-002: run states beside scores, ITT and conditional tables; the full report with negative findings and fairness deviations is B08 |

## Blocked or waiting cards (the checker prints these as notices)

B06-T04.01 on running Neo4j without Docker (OQ12); B07-T04.01 on Palladion shipping a critic switch (OQ11 answered: FEATURE_NOT_SUPPORTED until then); B08-T03.01 on OQ10 (confirmatory pairings, owner deferred; must be answered before the seal);
B08-T07.01 on OQ09 (dataset license, owner deferred; must be answered before then); B08-T01.02 on the paraphrase gate. Before the seal the owner relabels the pilot packet or accepts the delegated reading, and the synthesis golds are corrected (BR29).

## Next action

Palladion's limits are split into what we mitigate and what its contributor must fix in [PALLADION_FIXES](PALLADION_FIXES.md) (BADR-0027, E-B04-006). Next: B05 needs its own pre-phase adversary and scope authorization. The owner may relabel the packet with the [labelling guide](OWNER_LABELLING_GUIDE.md) at any time. B05 needs its own pre-phase adversary and scope. Open decisions that gate later work: OQ09, OQ10 and OQ12.
