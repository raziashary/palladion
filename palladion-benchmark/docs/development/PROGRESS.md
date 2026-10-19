# Current progress

Updated 2026-10-19. Atomic task state lives in the [master plan](MASTER_DEV_PLAN.md);
command observations and review receipts live in the [evidence log](EVIDENCE_LOG.md).

## Current checkpoint

B03 (evaluation core) is BUILT and audited: all eight cards are done and proven (E-B03-002 to E-B03-004), with the pre-phase adversary in E-B03-001. The scorers cover identity and text alignment, SlotCoverage and CompleteSet, ranking and provenance metrics, paired statistics, latency and cost, scorecards and a score-run driver, and the perfect, empty and shuffled controls run through the real Runner with an injected registry. `uv run pytest` passes 790 tests with ruff and strict mypy clean; every planted defect is killed. B02 is built with one open card: B02-T07.02 (pilot label audit) waits for the owner's labels (E-B02-005); the S-tier fixture has 1,200 fictional documents and 100 pilot questions.


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
| B02 | IN_PROGRESS | Built, E-B02-001 to E-B02-005; B02-T07.02 awaits the owner's labels (the model pass is done) |
| B03 | DONE | E-B03-001 to E-B03-004; the metrics are proven against the controls, not yet against any real arm |
| B04 | PLANNED | Depends on B02, B03; needs Palladion's interface (OQ03) |
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
| BG-GOLD | PARTIAL | E-B02-002, E-B02-005: schema, mapping, slots, family-grouped partitions and gold-support checks pass; the two-reader audit is open (owner labels pending) |
| BG-METRIC | PARTIAL | E-B03-002, E-B03-003: retrieval, evidence-set, cost and latency metrics with hand-computed cases and controls; answer-level metrics (B05), graph and system metrics (B06, B07) remain |
| BG-STATS | PARTIAL | E-B03-002, E-B03-003: known effect, simulated coverage, clustering, exact tests and bounds; power sizing and preregistered pairings remain (B08) |
| BG-ADAPTER | PARTIAL | Registry, capability matrix and contract tests exist (E-B01-003); no real adapter yet, so B04, B06 and B07 obligations remain |
| BG-FAIR | NOT_RUN | B04 |
| BG-TRACKA | NOT_RUN | B04 |
| BG-TRACKB | NOT_RUN | B05 |
| BG-TRACKC | NOT_RUN | B07 |
| BG-SECURITY | PARTIAL | Secret scan, key handling and the arm-visible allowlist (E-B01-002, E-B01-003); tenant and role visibility in the manifest, the barrier scan of the published tree, existence-hiding live reads and inert injection documents (E-B02-002); retriever-side enforcement remains for B04 onward |
| BG-PREREG | NOT_RUN | B08 |
| BG-ABLATION | NOT_RUN | B08 |
| BG-REPRO | PARTIAL | Manifest and ledger digests, deterministic config digests (E-B01-003); same-seed corpus digests across processes (E-B02-002); result validation remains for B04 |
| BG-REPORT | PARTIAL | E-B03-002: run states beside scores, ITT and conditional tables; the full report with negative findings and fairness deviations is B08 |

## Blocked or waiting cards (the checker prints these as notices)

B04-T03.01 on reading Palladion's live interface (OQ03); B06-T04.01 on running Neo4j without Docker (OQ12); B04-T01.02 and B04-T02.02 on reading Palladion's pins (OQ04, OQ05 answered; the reranker download needs the owner's yes);
B07-T04.01 on Palladion shipping a critic switch (OQ11 answered: FEATURE_NOT_SUPPORTED until then); B08-T03.01 on OQ10 (confirmatory pairings, owner deferred; must be answered before the seal);
B08-T07.01 on OQ09 (dataset license, owner deferred; must be answered before then); B08-T01.02 on the paraphrase gate. B02-T07.02 waits for the owner's labels.

## Next action

B04 (retrieval arms and the Track A pilot) needs its own pre-phase adversary and owner scope; it is not started. Owner action outstanding: label the 30-item packet (see the dataset card). Open decisions that gate later work: OQ03, OQ09, OQ10 and OQ12.
