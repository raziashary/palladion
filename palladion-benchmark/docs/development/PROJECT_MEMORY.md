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

Accepted: BADR-0001 to BADR-0037 (all; BADR-0031 to BADR-0037 are the B06 decisions: scope, live extraction limits, resumes on other models, and the private-experiment posture; BADR-0018 to BADR-0023 are the B02 decisions, BADR-0024 B03, BADR-0025 B04, BADR-0026 to BADR-0029 the audit, alias, B05 and live-use decisions, BADR-0030 the deferred owner items). All BADRs are accepted as of 2026-10-20 (BADR-0006 phase breakdown, BADR-0008 one model per question, BADR-0013 benchmark-local .env). Still open and tracked: OQ03 (read Palladion's interface at B04), OQ09 (license, before B08-T07.01), OQ10 (pairings, before B08-T03.01), OQ13 (label audit stance, before B08-T03.01). Open questions OQ01–OQ13 in [risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## What exists in code (B01)

- `benchmark/contracts.py` (typed requests, candidates, case responses, run states, failure mapping), `config.py` (strict YAML loaders, pins), `registry.py` (15 arms, capability declarations),
  `run_manifest.py` (immutable manifest, read-only git capture), `tracing.py` (stage spans, call budgets), `runner.py` (paired ITT runner, ledger, plan registry), `cli.py`, `generator.py` (Groq pool, live proof
  entry point), `secret_scan.py`. Evidence: E-B01-002 to E-B01-006 (371 tests). Nothing yet touches Palladion, a corpus or a retriever.
- Commands from `palladion-benchmark/`: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check benchmark tests`, `uv run mypy`, `uv run python -m benchmark.cli capability-matrix`,
  `uv run python -m benchmark.secret_scan --staged`. `make` is not installed and Docker cannot run on the author's machine; Qdrant runs Docker-free under WSL (BADR-0017, launcher built in B04).
- The live generator proof (3 calls, 3 of 3 approved models answered) is the only provider use so far; the key lives in the gitignored `palladion-benchmark/.env` and has never been printed.
- Free-tier limits seen: 8,000 tokens per minute on each approved model. Pre-assignment budgets stay null until daily limits are stated (BADR-0015).

## What exists in code (B06)

- `benchmark/llm_proxy.py` (counting proxy: call, token, completion and model caps, pace, local embeddings, per-run bearer token, worst-case charging, stop at a daily limit, timestamped book), `comparators/protocol.py` (worker protocol and the loopback-only guard), `benchmark/adapters/worker.py` (`ComparatorWorker`, `WorkerArm`, `launch_arm`: allow-listed environment, `LITELLM_MODE=PRODUCTION`), `comparators/{hipporag2,graphrag,lightrag}/worker.py` with thin adapters `benchmark/adapters/{hipporag2,graphrag,lightrag}.py`, `benchmark/eval/graph_metrics.py` (four metrics defined, four declared undefined), `benchmark/subset.py` and `scripts/{comparators,build_subset,run_graph_arms}.py` (`--resume-from`, `--reconstruct`), additive contract fields (pin, extraction cost, relation).
- Key facts: comparators run in their own pinned Python 3.12 environments under gitignored `artifacts/comparators/`; the key stays in the proxy; R7b is FEATURE_NOT_SUPPORTED at the pin (PF07 has since landed in Palladion, so a re-pin is needed); a failed build that names its error is a recorded result; the free tier (200,000 tokens per day per model) stopped the live pilot after R6 reached 63 of 103 chunks (BR39). Matched baseline R0 to R3 ran on `artifacts/fixtures/Ssub60`.
- Evidence: E-B06-001 to E-B06-005. No graph arm has a measured retrieval result; the benchmark is the owner's private experiment (BADR-0037).

## What exists in code (B05)

- `benchmark/fixtures/answer_gold.py` (evaluator-only answer targets in `answers_<split>.jsonl`, own digest, bound to the question file by digest); optional `Claim.kind/params` and `CaseResponse.action/policy_outcome/version_ids/from_payload`; `benchmark/generator.py` (fault classification, `deadline`, `cancel`, prompt screen and record, `screen_prompts=False` only for the evaluator-side label audit); `benchmark/eval/{answer_case,citations,claims,policy,abstention,score_answers,judge_audit}.py`; `benchmark/track_b.py`, `scripts/run_track_b.py`, `scripts/score_track_b.py`; the Track B branch of `results_check.py`; `render_answer_scorecard` in `analysis/tables.py`; `docs/scoring_rubric.md`, `docs/annotation_guide.md`.
- Key facts: Track B reuses the Runner (a retriever plus the shared generator is a system arm); the prompt, schema, budget and gate are identical for every arm; what the generator was shown is read from `prompts.jsonl`; labels are keyed by question, arm, claim and citation; a judge label never stands over a human or deterministic one; one bounded live pass has run (E-B05-005); the offline stand-in is `ExtractiveStubTransport`; the Track B split list is smoke only until dev gold exists.
- Evidence: E-B05-001 to E-B05-006. One live pass ran (BADR-0029, 16 calls, R2 and R3, 8 questions); any more live use needs a new owner instruction. A rejected answer now names its rule in the ledger flags (BR33 fixed).

## What exists in code (B04)

- `benchmark/adapters/`: `common.py` (published-namespace view, chunker, whitespace-word counts, neutral ACL filter C1/C2, budget enforcer, harness-attributed candidates, ledger flags), `models.py` (pinned model fetch and verify), `bm25.py` (R0), `dense.py` (R1, Qdrant HNSW, recorded ANN recall), `hybrid.py` (R2 fusion, R3 rerank), `palladion.py` (R7a over HTTP only). `benchmark/track_a.py` builds the local arms and runs Track A through the real Runner; `benchmark/results_check.py` validates a run directory. Scripts: `qdrant_server.py` (checksum-pinned, WSL, port 17333), `palladion_runtime.py` (detached worktree at 6444345, own root, collection and port 18081), `build_indices.py`, `run_track_a.py`, `score_track_a.py`, `validate_results.py`.
- Key facts: pins live in `configs/comparators.yaml` with revisions and file digests; R7a sees only what Palladion's HTTP API returns, mapped to published documents through a revision table; documents loaded over HTTP get no identifier aliases (BR24); never run the Palladion runtime on Palladion's own root, port 18080 or collection `knowledge_chunks_v1`; models, binaries and indexes are under gitignored `artifacts/`. Evidence E-B04-001 to E-B04-004 (981 tests). Pilot waits for the owner's labels ([guide](OWNER_LABELLING_GUIDE.md)).
- The tests start the benchmark's Qdrant and a real isolated Palladion (about 15 minutes for the whole suite); the real-runtime test creates the worktree under `artifacts/` if it is missing.

## What exists in code (B03)

- `benchmark/eval/`: `normalize.py` (locator grammar, identity vs text alignment, exposure), `evidence_sets.py` (SlotCoverage, CompleteSet), `retrieval.py` (ranking and provenance metrics), `statistics.py` (cluster bootstrap, McNemar, Holm, TOST, zero-failure bound, calibration, power), `cost_latency.py`, `score_run.py` (driver, integrity checks, control arms, per-stratum separation); `benchmark/analysis/tables.py` (scorecards). Rules are in BADR-0024 and its amendment.
- Key facts: headline metrics use identity only; harm metrics are conditional-only; a non-completed pair is zero in ITT for benefit metrics the gold says apply; the scorer refuses a ledger hole, a gold, corpus or manifest mismatch; controls live in `score_run.py` and never in the production registry. Evidence E-B03-001 to E-B03-004 (790 tests). Limits: BR18 to BR20.
- Do not run `ruff format .` from the project root: it reformats the protocol and the checker. Format `benchmark tests scripts` only.

## What exists in code (B02)

- `benchmark/fixtures/`: `entities.py` (vocabulary), `knowledge.py` (versions, policies, as-of selection, evaluator, graph), `operations.py` (timelines, case histories), `world.py` (aggregate and tier seed), `phrasebook.py` (EN/ID banks and question templates), `documents.py` (rendering, equivalence check, measurement), `artifacts.py` (support documents, noise, corpus pipeline), `manifest.py` (manifests, four namespaces, barrier scan), `questions.py` (gold schema, screening, partitions), `question_gen.py` (ten stratum generators), `live_api.py` (read-only mock), `validation.py` (integrity and realism checks), `audit.py` (label audit). `scripts/generate_data.py` builds the S tier; `docs/dataset_card.md` carries its figures.
- Evidence: E-B02-001 to E-B02-006 (654 tests). Generated data is under the gitignored `artifacts/fixtures/S/`; the label-audit packet and the label file (written by the coordinator under delegation, E-B02-006) are in its `generator/audit/` folder and must not be regenerated over (labels are kept, but check the gold digest).
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


## What exists in code (B07)

- Palladion (separate unpushed commits `4af66d6`, `eec4ba5`, `1feef14`): counted model transport, evaluator mode with a response `evaluator` block, a registry-owned evaluation clock. Pin `eec4ba5` (BADR-0041).
- `benchmark/adapters/{langchain,langgraph,google_adk,palladion_system}.py` (E0, E1, E2 NOT_RUN, E3/E4), `comparators/langchain/worker.py`, `benchmark/fixtures/{episodes,updates,mutations}.py`, `benchmark/eval/{memory,critic,tool_use,observable}.py` and the update-consistency section of `eval/cost_latency.py`, `benchmark/mutations_apply.py`, `benchmark/track_c.py`, `benchmark/scripted_provider.py`, `scripts/run_track_c.py`.
- Key facts: E3 is Palladion's own critic-off control and a distinct treatment (BADR-0039); counts come from each arm's counting proxy; a measure no interface exposes is `NotObservable`, never zero; Palladion episodes are isolated by principal and session in the corpus case (BADR-0041); E3 and E4 run one at a time; a Palladion turn cost a mean 14,204 prompt tokens in the pilot (BR47); the live pilot is partial (E-B07-003, BADR-0042).
- Evidence: E-B07-001 to E-B07-004. No system arm has a measured result that supports a ranking.
