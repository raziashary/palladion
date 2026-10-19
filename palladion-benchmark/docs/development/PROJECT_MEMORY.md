# Benchmark working memory

Updated 2026-10-19. Navigation aid only; the user, the protocol, source and ADRs retain authority.

## Stable facts

- Repository root `C:/palladion`; benchmark root `palladion-benchmark/`; branch `main` with upstream `origin/main`. The system under
  test is `palladion/`, developed concurrently by another contributor in the same working tree (uncommitted edits exist there).
- The vision is the [research protocol v1.0](../vision/palladion_retrieval_benchmark_research_protocol.md), 22 sections. It proposes
  eight retrievers (R0–R7), five systems (E0–E4), three tracks, a fictional payment firm (Meridian Switchworks), 1,000 questions,
  100 episodes and 16 ablations. All sizes and thresholds are starting proposals until sealed. No comparative result has been measured.
- The protocol's repository tree has 70 files (56 Python, 14 other), verified by parsing the tree (E-B00-001). The plan adds
  `benchmark/generator.py`, `tests/test_generator_pool.py` and `docs/dataset_card.md` (BADR-0010).
- Primary challengers: R3 (hybrid plus reranker) and E3 (Palladion without critic). Claims are bounded: more complete applicable
  evidence and fewer unsupported directives at acceptable cost, not "best RAG".
- Owner answers (2026-10-18): in-repo uv project; generator pool Groq qwen/qwen3.8-27b, openai/gpt-oss-120b, openai/gpt-oss-20b (rate-limit
  driven); template-first corpus; Haiku 5.5 subagents only and only as needed; push to main allowed; libraries may be added.
- The benchmark reaches Palladion by HTTP adapter only; it never imports or edits Palladion code (BADR-0002).
- Environment seen: Windows 11, Python 3.14.7, uv 0.13.1, Git Bash and PowerShell. Palladion itself uses WSL for Qdrant (Docker-free).

## Locked decisions and open items

Accepted: BADR-0001 to BADR-0023 (all; BADR-0018 to BADR-0023 are the B02 decisions). All BADRs are accepted as of 2026-10-18 (BADR-0006 phase breakdown, BADR-0008 one model per question, BADR-0013 benchmark-local .env). Still open and tracked: OQ03 (read Palladion's interface at B04), OQ09 (license, before B08-T07.01), OQ10 (pairings, before B08-T03.01). Open questions OQ01–OQ11 in [risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## What exists in code (B01)

- `benchmark/contracts.py` (typed requests, candidates, case responses, run states, failure mapping), `config.py` (strict YAML loaders, pins), `registry.py` (15 arms, capability declarations),
  `run_manifest.py` (immutable manifest, read-only git capture), `tracing.py` (stage spans, call budgets), `runner.py` (paired ITT runner, ledger, plan registry), `cli.py`, `generator.py` (Groq pool, live proof
  entry point), `secret_scan.py`. Evidence: E-B01-002 to E-B01-006 (371 tests). Nothing yet touches Palladion, a corpus or a retriever.
- Commands from `palladion-benchmark/`: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check benchmark tests`, `uv run mypy`, `uv run python -m benchmark.cli capability-matrix`,
  `uv run python -m benchmark.secret_scan --staged`. `make` is not installed and Docker cannot run on the author's machine; Qdrant runs Docker-free under WSL (BADR-0017, launcher built in B04).
- The live generator proof (3 calls, 3 of 3 approved models answered) is the only provider use so far; the key lives in the gitignored `palladion-benchmark/.env` and has never been printed.
- Free-tier limits seen: 8,000 tokens per minute on each approved model. Pre-assignment budgets stay null until daily limits are stated (BADR-0015).

## What exists in code (B03)

- `benchmark/eval/`: `normalize.py` (locator grammar, identity vs text alignment, exposure), `evidence_sets.py` (SlotCoverage, CompleteSet), `retrieval.py` (ranking and provenance metrics), `statistics.py` (cluster bootstrap, McNemar, Holm, TOST, zero-failure bound, calibration, power), `cost_latency.py`, `score_run.py` (driver, integrity checks, control arms, per-stratum separation); `benchmark/analysis/tables.py` (scorecards). Rules are in BADR-0024 and its amendment.
- Key facts: headline metrics use identity only; harm metrics are conditional-only; a non-completed pair is zero in ITT for benefit metrics the gold says apply; the scorer refuses a ledger hole, a gold, corpus or manifest mismatch; controls live in `score_run.py` and never in the production registry. Evidence E-B03-001 to E-B03-004 (790 tests). Limits: BR18 to BR20.
- Do not run `ruff format .` from the project root: it reformats the protocol and the checker. Format `benchmark tests scripts` only.

## What exists in code (B02)

- `benchmark/fixtures/`: `entities.py` (vocabulary), `knowledge.py` (versions, policies, as-of selection, evaluator, graph), `operations.py` (timelines, case histories), `world.py` (aggregate and tier seed), `phrasebook.py` (EN/ID banks and question templates), `documents.py` (rendering, equivalence check, measurement), `artifacts.py` (support documents, noise, corpus pipeline), `manifest.py` (manifests, four namespaces, barrier scan), `questions.py` (gold schema, screening, partitions), `question_gen.py` (ten stratum generators), `live_api.py` (read-only mock), `validation.py` (integrity and realism checks), `audit.py` (label audit). `scripts/generate_data.py` builds the S tier; `docs/dataset_card.md` carries its figures.
- Evidence: E-B02-001 to E-B02-005 (654 tests). Generated data is under the gitignored `artifacts/fixtures/S/`; the label-audit packet and the owner's label file are in its `generator/audit/` folder and must not be regenerated over (labels are kept, but check the gold digest).
- Providers: the B02 label audit used 36 + 37 calls on an earlier build and 36 on the final fixture; no live call is authorised now (BADR-0019).

## Reading order for a fresh session

1. [AGENTS](../../AGENTS.md), then [GOAL](GOAL.md) and [PROGRESS](PROGRESS.md).
2. The parent row and atomic card in the [master plan](MASTER_DEV_PLAN.md), the ADRs it cites and the protocol sections it names.
3. Palladion's live source and its own [progress](../../../palladion/docs/development/PROGRESS.md) before any adapter work.

## Operating notes

- Stage explicit `palladion-benchmark/` paths only; check `git diff --cached --name-only` before commit and `git log origin/main..HEAD` before push.
- Run the checker with `python palladion-benchmark/docs/development/check_docs.py` from the repository root.
- Provider calls need an explicit enable flag and a provisioned key; none exists yet. Never read or copy Palladion's `.env`.
- Reviewer subagents: Haiku 5.5, read-only, complete protocol, no credentials, no git.
