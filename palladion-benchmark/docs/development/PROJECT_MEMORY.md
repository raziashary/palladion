# Benchmark working memory

Updated 2026-10-18. Navigation aid only; the user, the protocol, source and ADRs retain authority.

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

Accepted: BADR-0001–0005, 0007–0012. All BADRs are accepted as of 2026-10-18 (BADR-0006 phase breakdown, BADR-0008 one model per question, BADR-0013 benchmark-local .env). Still open and tracked: OQ03 (read Palladion's interface at B04), OQ09 (license, before B08-T07.01), OQ10 (pairings, before B08-T03.01). Open questions OQ01–OQ11 in [risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## Reading order for a fresh session

1. [AGENTS](../../AGENTS.md), then [GOAL](GOAL.md) and [PROGRESS](PROGRESS.md).
2. The parent row and atomic card in the [master plan](MASTER_DEV_PLAN.md), the ADRs it cites and the protocol sections it names.
3. Palladion's live source and its own [progress](../../../palladion/docs/development/PROGRESS.md) before any adapter work.

## Operating notes

- Stage explicit `palladion-benchmark/` paths only; check `git diff --cached --name-only` before commit and `git log origin/main..HEAD` before push.
- Run the checker with `python palladion-benchmark/docs/development/check_docs.py` from the repository root.
- Provider calls need an explicit enable flag and a provisioned key; none exists yet. Never read or copy Palladion's `.env`.
- Reviewer subagents: Haiku 5.5, read-only, complete protocol, no credentials, no git.
