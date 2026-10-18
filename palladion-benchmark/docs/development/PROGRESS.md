# Current progress

Updated 2026-10-18. Atomic task state lives in the [master plan](MASTER_DEV_PLAN.md);
command observations and review receipts live in the [evidence log](EVIDENCE_LOG.md).

## Current checkpoint

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
| B02 | PLANNED | Depends on B01; awaits owner GO |
| B03 | PLANNED | Depends on B02 gold schema |
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
| BG-FIXTURE | NOT_RUN | B02 |
| BG-GOLD | NOT_RUN | B02 |
| BG-METRIC | NOT_RUN | B03 |
| BG-STATS | NOT_RUN | B03 |
| BG-ADAPTER | PARTIAL | Registry, capability matrix and contract tests exist (E-B01-003); no real adapter yet, so B04, B06 and B07 obligations remain |
| BG-FAIR | NOT_RUN | B04 |
| BG-TRACKA | NOT_RUN | B04 |
| BG-TRACKB | NOT_RUN | B05 |
| BG-TRACKC | NOT_RUN | B07 |
| BG-SECURITY | PARTIAL | Secret scan with controls, key handling on every error path, arm-visible allowlist (E-B01-002, E-B01-003); tenant, ACL and injection obligations remain for B02 onward |
| BG-PREREG | NOT_RUN | B08 |
| BG-ABLATION | NOT_RUN | B08 |
| BG-REPRO | PARTIAL | Manifest and ledger digests, deterministic config digests (E-B01-003); same-seed corpus digests and result validation remain for B02 and B04 |
| BG-REPORT | NOT_RUN | B03, B08 |

## Blocked or waiting cards (the checker prints these as notices)

B04-T03.01 on reading Palladion's live interface (OQ03); B06-T04.01 on running Neo4j without Docker (OQ12); B04-T01.02 and B04-T02.02 on reading Palladion's pins (OQ04, OQ05 answered; the reranker download needs the owner's yes);
B07-T04.01 on Palladion shipping a critic switch (OQ11 answered: FEATURE_NOT_SUPPORTED until then); B08-T03.01 on OQ10 (confirmatory pairings, owner deferred; must be answered before the seal);
B08-T07.01 on OQ09 (dataset license, owner deferred; must be answered before then); B08-T01.02 on the paraphrase gate. Phase B02 does not start until the owner says GO.

## Next action

Wait for the owner's GO on B02. B02 starts with its own pre-phase Haiku 5.5 adversary. Open decisions that gate later work: OQ03, OQ09, OQ10 and OQ12.
