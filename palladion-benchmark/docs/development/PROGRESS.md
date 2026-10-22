# Current progress

Updated 2026-10-22. Atomic task state lives in the [master plan](MASTER_DEV_PLAN.md);
command observations and review receipts live in the [evidence log](EVIDENCE_LOG.md).

## Current checkpoint

B07 (system arms, memory, critic and mutations) is DONE with a partial live pilot (E-B07-002 to E-B07-004): the adversary (E-B07-001) and your scope decisions (BADR-0038 to BADR-0042) shaped 19 cards, all closed. Built and proven offline: the Palladion changes (three separate unpushed commits, `4af66d6`, `eec4ba5`, `1feef14`), one new pin, E0 and E1 in the real LangChain and LangGraph environment, E2 as NOT_RUN, E3 and E4 over Palladion's message interface, 1,000 document events and seven kinds of episodes, the memory, update-consistency, critic and tool-use measures with NOT_OBSERVABLE kept apart from zero, the 19 mutations and 7 invariants as operations on the real fixture with their application to each kind of system, and the Track C runner with four memory baselines. Two entry-point smokes ran the whole path with a scripted provider (E2 to E4, and E0 and E1). The live pilot ran only for E3 (BADR-0042): a harness timeout wasted the first attempt (77,000 tokens), the second answered 3 of 8 turns before the provider's daily limit and its per-minute limit bit; a Palladion turn cost a mean 14,204 prompt tokens against a scripted estimate of 4,581, E4 was not run (the day's quota was spent; you chose to close), and E0 and E1 were not run live. No system arm has a result that supports a ranking. The Palladion commits wait for your approval to push; the evaluation-clock change was not on the list you approved by name.

B06 (graph and research comparators) is STARTED: the pre-phase adversary ran (E-B06-001, 16 findings) and the owner decided the scope (BADR-0031). The plan now has three foundation cards (additive contracts, a comparator worker with a counting proxy, approved pins and downloads), the three comparator adapters, R7b as FEATURE_NOT_SUPPORTED with PF07 requested, four graph metrics the data supports, and a cold-state pilot on a matched subset. All nine cards are done (E-B06-002 to E-B06-005), the ninth (B06-T06.01, the live pilot) with the limits below, accepted by the owner: the contracts, the worker and counting proxy, the pins, the three adapters on the real upstream code behind a fake provider, R7b as unsupported at the pin (PF07 has since landed in Palladion; a re-pin is needed), and the graph metrics. The live cold-state pilot ran only partly (E-B06-004, BADR-0032 to BADR-0037): R6 LightRAG indexed 63 of 103 chunks over six attempts and three models (410 provider calls, 667,995 tokens) before every approved model reached Groq's 200,000-tokens-per-day limit, so it never answered a query; R4 and R5 were not run live (quota-blocked, nothing spent). The matched baseline R0 to R3 ran on the same 60-document subset (48 pairs, validated and scored); R7a was not. The end-of-phase audit (E-B06-005, 18 findings) is resolved: the provider key can no longer reach a comparator through litellm, all three workers are loopback-only, the proxy charges worst cases and stops at a daily limit, and a failed or interrupted run keeps its spend record. The Haiku-implementer permission of BADR-0031 ends with B06. The full S tier is not run on the free tier (an estimate of 4 million tokens and 8 hours per system).

B05 (answer-level evaluation and Track B) is DONE: all eleven cards are done (E-B05-002 to E-B05-005; the pre-phase adversary is E-B05-001). The first bounded live pass ran R2 and R3 over 8 questions with the primary Groq model: 16 of 20 authorized calls, 15 pairs OK and 1 invalid answer (cause not recorded, BR33), no rate limit and no failover; it is descriptive and supports no ranking (E-B05-005). The answer-gold, the citation, claim, policy and abstention scorers, the loss sweep, the label store and judge audit, the Track B runner, scorer and validator exist and were run end to end on the real corpus with an offline stand-in generator (261 of 261 pairs). R7a, the rest of the smoke split and any larger live pass wait for your instruction. B04 (Track A arms and pilot) is DONE: all fourteen cards are done and proven (E-B04-002 to E-B04-005; the pre-phase adversary is E-B04-001). The pilot ran R0 to R3 and R7a on the smoke split under C2 and C1 (500 of 500 pairs each, 97 questions scored after withdrawing three defective synthesis questions); the observations are in E-B04-005 and support no ranking claim. The shared harness, a Docker-free Qdrant launcher, R0 to R3 with Palladion's pinned models, an isolated Palladion runtime with the HTTP-only R7a adapter, the build, run, score and validate commands all exist; `uv run pytest` passes 981 tests with ruff and strict mypy clean, every planted defect is killed, and two real smokes (R0 to R3 and R7a over the full corpus) pass the validator. They are not the pilot and support no ranking claim.

B03 (evaluation core) is BUILT and audited: all eight cards are done and proven (E-B03-002 to E-B03-004), with the pre-phase adversary in E-B03-001. The scorers cover identity and text alignment, SlotCoverage and CompleteSet, ranking and provenance metrics, paired statistics, latency and cost, scorecards and a score-run driver, and the perfect, empty and shuffled controls run through the real Runner with an injected registry. `uv run pytest` passes 790 tests with ruff and strict mypy clean; every planted defect is killed. B02 is built; its last card, the pilot label audit, was done under delegation (E-B02-006); the S-tier fixture has 1,200 fictional documents and 100 pilot questions.


B01 (harness foundation) is DONE: all eleven cards are built and proven (E-B01-002 to E-B01-004), the pre-phase Haiku 5.5 adversary (E-B01-001) and the post-phase audit with its resolution check (E-B01-005, E-B01-006) are dispositioned. The harness has typed contracts, strict configs, a 15-arm capability registry, an immutable manifest, tracing and
call budgets, a paired runner with intention-to-treat records, a CLI, a secret scanner and a generator pool. `uv run pytest` passes 371 tests, ruff and strict mypy are clean,
and the real entry point reached all three approved Groq models once each. No dataset, retriever, Palladion call or measurement exists. `make` is not installed and Docker cannot run
on this machine (owner, 2026-10-18), so the Makefile and the compose file were checked statically only; Qdrant will run Docker-free under WSL (BADR-0017).

Decisions in force: in-repo uv project (BADR-0001); generator pool qwen/qwen3.8-27b, openai/gpt-oss-120b, openai/gpt-oss-20b with per-question pre-assignment and no automatic switch
(BADR-0007, BADR-0008, BADR-0015); template-first corpus (BADR-0009); Haiku 5.5 reviewers only (BADR-0003); push to main allowed (BADR-0004); benchmark-local `.env` (BADR-0013);
phase plan approved (BADR-0006); dependencies and extra files (BADR-0014); required citation field, subprocess isolation from B04 and pinned system-under-test checkout (BADR-0016); no Docker, Qdrant as a standalone binary under WSL (BADR-0017).
Still open and tracked: OQ03 (read Palladion's interface at B04), OQ09 (license, before B08-T07.01), OQ10 (pairings, before B08-T03.01) and OQ13 (label audit stance, before B08-T03.01); see
[risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## Phase state

| Phase | State | Evidence / next action |
|---|---|---|
| B00 | DONE | E-B00-001 to E-B00-004 |
| B01 | DONE | E-B01-001 to E-B01-006 |
| B02 | DONE | E-B02-001 to E-B02-006; the label audit was made by the coordinator under the owner's delegation (BADR-0026), so BG-GOLD stays PARTIAL |
| B03 | DONE | E-B03-001 to E-B03-004; the metrics are proven against the controls, not yet against any real arm |
| B04 | DONE | E-B04-001 to E-B04-005; the pilot is exploratory, smoke split only |
| B05 | DONE | Built and audited, E-B05-001 to E-B05-005; the first live pass (16 calls) is descriptive only |
| B06 | DONE | Built and audited, E-B06-001 to E-B06-005; the live graph pilot is partial (R6 63 of 103 chunks, no query answered; R4 and R5 not attempted; BR39) and no graph arm has a measured result |
| B07 | DONE | E-B07-001 to E-B07-004; the live pilot is partial (E3 3 of 8 turns, E4 NOT_RUN, E0 and E1 not live; BR47) and no system arm has a measured ranking result |
| B08 | RE-PLANNED | BADR-0043: a descriptive, exploratory comparison of Palladion with the other systems under the free tier (cards B08-T08.01 to T08.06: re-pin, Track A, Track B, Track C, graph arms, report); T01 to T05 are not run on this path |
| B09 | DEFERRED | Conditional replication and stress |

## Gate state

| Gate | State | Evidence and limits |
|---|---|---|
| BG-DOC | PASS | Checker and self-test in E-B00-001; independent review E-B00-003. Structural plus one model review only |
| BG-HARNESS | PASS | E-B01-002 to E-B01-006: contracts, budgets, generator, ITT runner, CLI and the live entry-point proof (3 of 3 models), audited. Covers the B01 contract only; it does not test any system under test |
| BG-FIXTURE | PARTIAL | E-B02-002, E-B02-003: determinism across processes, referential, contradiction, merge identity, temporal, leakage and realism checks with planted-defect controls on the S tier. The 19 mutations and the M tier remain (B07-T07, B08-T01) |
| BG-GOLD | PARTIAL | E-B02-002, E-B02-005: schema, mapping, slots, family-grouped partitions and gold-support checks pass; the label audit is done but by one non-independent reader (29 of 30 agree with the gold, E-B02-006); the owner's relabel or acceptance is due before the seal |
| BG-METRIC | PARTIAL | E-B03-002, E-B03-003: retrieval, evidence-set, cost and latency metrics with hand-computed cases and controls; answer-level metrics have hand-computed cases and controls (E-B05-002, E-B05-003); the four graph metrics the data supports exist with controls (E-B06-002), system-level metrics (B07) remain |
| BG-STATS | PARTIAL | E-B03-002, E-B03-003: known effect, simulated coverage, clustering, exact tests and bounds; power sizing and preregistered pairings remain (B08) |
| BG-ADAPTER | PARTIAL | Registry and contract tests (E-B01-003); five real adapters with capabilities proven in tests and two real smokes (E-B04-002); three graph comparator adapters proven offline against a fake provider (E-B06-002); no graph arm produced a measured result (BR39); B07 arms remain |
| BG-FAIR | PARTIAL | E-B04-002: one chunker, filter, budget and tie rule for R0 to R3, C1 and C2 differ only in the filter, R7a's differences declared (BR22, BR24, BR27, BR28); equal-budget claims need the pilot |
| BG-TRACKA | PARTIAL | E-B04-002: runner, scorer and validator work on real runs; the pilot ran (E-B04-005); the sealed confirmatory run is B08-T04.01 |
| BG-TRACKB | PARTIAL | E-B05-002, E-B05-005: runner, scorer and validator pass on a real-corpus stand-in run and on a 16-pair live qwen run; R7a, the full split and repetitions are not run |
| BG-TRACKC | PARTIAL | E-B07-002 to E-B07-004: runner, isolation, baselines, counts from the book and run states proven offline and in two scripted smokes; one live arm (E3) answered 3 of 8 turns; E4, E0 and E1 not run live; no confirmatory claim |
| BG-SECURITY | PARTIAL | Secret scan, key handling and the arm-visible allowlist (E-B01-002, E-B01-003); tenant and role visibility in the manifest, the barrier scan of the published tree, existence-hiding live reads and inert injection documents (E-B02-002); retriever-side enforcement remains for B04 onward |
| BG-PREREG | NOT_RUN | B08 |
| BG-ABLATION | NOT_RUN | B08 |
| BG-REPRO | PARTIAL | Manifest and ledger digests, deterministic config digests (E-B01-003); same-seed corpus digests across processes (E-B02-002); result validation exists and passes real runs (E-B04-002); the sealed confirmatory run is B08 |
| BG-REPORT | PARTIAL | E-B03-002: run states beside scores, ITT and conditional tables; the full report with negative findings and fairness deviations is B08 |

## Blocked or waiting cards (the checker prints these as notices)

B06 live completion of R4 to R6 on fresh free-tier quota (BR39, optional, owner's call at B08); B07-T04.01 on Palladion shipping a critic switch (OQ11 answered: FEATURE_NOT_SUPPORTED until then); B08-T03.01 on OQ10 (confirmatory pairings, owner deferred; must be answered before the seal) and OQ13 (owner relabels the pilot packet or accepts the delegated labels in writing; deferred 2026-10-20);
B08-T07.01 on OQ09 (dataset license, owner deferred; must be answered before then); B08-T01.02 on the paraphrase gate. The synthesis golds are corrected before the seal (BR29).

## Next action

BADR-0043 (2026-10-22): start with B08-T08.01 (re-pin Palladion to `dd70c0e`, re-run the gates), then B08-T08.02 (Track A on the full S tier: no model, no quota). Live days (Track B, Track C, graph arms) run under the BADR-0042 caps; the live-day order and the matched lists are fixed before the first spend. Open and unchanged: OQ09, OQ10, OQ13 (defaults accepted for the exploratory path).
