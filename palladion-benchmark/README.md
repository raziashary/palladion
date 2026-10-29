# Palladion benchmark

**A controlled experiment on whether evidence-first retrieval and answering is measurably more reliable than
standard and strong RAG baselines.**

This folder holds the benchmark for [Palladion](../palladion/README.md): a retrieval and evidence-reliability study over a
fictional payment-support knowledge base (Meridian Switchworks). It is developed separately from the system under test and
reaches it only through an adapter. The design is the
[research protocol v1.0](docs/vision/palladion_retrieval_benchmark_research_protocol.md); its hypotheses H1–H8 are
**unmeasured**.

**Current state (2026-10-29):** the harness, the synthetic fixtures, the scorers and Track A are built and tested, and B08 has produced its main results. A **sealed, pre-registered, retrieval-only Track A run on six fresh fictional worlds** is done and confirms the registered comparison: Palladion finds the complete set of needed documents for 39.9% of questions against 22.6% for the tuned strong baseline (hybrid plus reranker), +17 points (95% range +12 to +23, above the registered 5-point bar), and +13 points over the same baseline given Palladion's approval-and-date rule ([E-B08-013](docs/development/EVIDENCE_LOG.md)). Every system was tuned equally first (bigger text pieces helped all of them; [E-B08-012](docs/development/EVIDENCE_LOG.md)); the way of judging is in [the pre-registration](docs/development/PREREGISTRATION_TRACK_A.md) and the seal checks nothing moved. On the public **BEIR SciFact** set (ordinary search, no versions or access rules) Palladion is on par with the strong baseline, 78.0% against 77.0% of 300 questions ([E-B08-014](docs/development/EVIDENCE_LOG.md)). Answering (Track B) at the current Palladion has 196 of 200 pairs and no score yet; the first full-Palladion whole-system run (E4) is void and will be re-run; the reworded-questions test, the graph systems and the final package are not done. The labels are the generator's and no human has checked them; one generator wrote the corpus, the questions and the labels. Hypotheses H1 to H8 are not claimed as confirmed. See [progress](docs/development/PROGRESS.md).

**Results so far, in plain words:** see the [report](../report.md) and the scorecard in the [repository README](../README.md#how-palladion-compares-today-plain-language-scorecard).

## What it will compare

- Retrievers R0–R7: BM25, dense, hybrid RRF, hybrid plus reranker, HippoRAG 2, GraphRAG Local, LightRAG and Palladion
  (without and with a bounded graph).
- Systems E0–E4: plain LangChain, LangGraph agentic, Google ADK with RAG Engine (if accessible), Palladion without and with its critic.
- Three tracks: A retrieval only, B controlled retrieval-to-answer with one shared generator, C native end-to-end.
- Ten question strata, 19 mutation cases and 7 metamorphic invariants, 16 ablations, with paired, family-clustered statistics.

Primary challengers are R3 and E3. A null result against a strong hybrid baseline is a valid outcome.

## Documentation

- [Documentation entry point](docs/README.md)
- [Master development plan](docs/development/MASTER_DEV_PLAN.md) and [atomic register](docs/development/MASTER_DEV_PLAN.md#atomic-execution-register)
- [Goal](docs/development/GOAL.md), [progress](docs/development/PROGRESS.md), [decisions](docs/development/ADR_LOG.md)
- [Testing gates](docs/development/TESTING_GATES.md), [operational protocol](docs/development/RESEARCH_PROTOCOL.md)
- [Project instructions](AGENTS.md)

Validate the documentation (standard library only, from the repository root):

```powershell
python palladion-benchmark/docs/development/check_docs.py
python palladion-benchmark/docs/development/check_docs.py --self-test
```

These commands check structure and references, not benchmark behavior or any research claim.

## Environment

Python tooling is managed with uv from this folder.

```powershell
cd palladion-benchmark
uv sync --locked
uv run ruff check .
uv run mypy
uv run pytest
uv run python -m benchmark.cli capability-matrix
```

Runtime dependencies are `httpx` and `PyYAML` (BADR-0014); others are added by the task that needs them. A `Makefile` wraps the
same commands for machines that have `make`. Docker is not used on the author's machine: Qdrant will run as a checksum-pinned standalone binary under WSL, as in Palladion (BADR-0017); `docker-compose.yml` is optional. Provider calls never happen implicitly: the generator needs the benchmark-local
`.env` (copy `.env.example`), an explicit `--enable-live` flag and a call budget, for example
`uv run python -m benchmark.generator --prove --enable-live`. Run `uv run python -m benchmark.secret_scan --staged` before committing; it fails on binary or oversized files it cannot read unless `--allow-unscannable` is passed.

## Track C (native end-to-end systems)

`uv run python scripts/run_track_c.py --root artifacts/fixtures/S --out artifacts/runs/c-smoke --run-id c-smoke --arms E2,E3,E4 --episodes 2 --mutations M01,M09` runs episodes and mutation cases against E0 to E4 with the offline scripted provider (no model, no key, no claim). It needs the isolated Palladion runtime (`scripts/palladion_runtime.py prepare`) and the benchmark's Qdrant for E3 and E4. A live run needs `--generator live --enable-live` and the owner's `--call-cap`, `--token-cap` and `--pace-seconds`; E3 and E4 are run one at a time on a freshly prepared runtime when mutation cases are included. Every arm's model calls are counted by its own proxy and the counts in the summary are that book.

## Limits

All data will be fictional and synthetic and is not an actual operating procedure. Synthetic worlds can be easier than real
knowledge, the author of the benchmark also builds Palladion, and a single-provider generator is a confound; the plan records
each as a risk with a mitigation owner.
