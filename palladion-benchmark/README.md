# Palladion benchmark

**A controlled experiment on whether evidence-first retrieval and answering is measurably more reliable than
standard and strong RAG baselines.**

This folder holds the benchmark for [Palladion](../palladion/README.md): a retrieval and evidence-reliability study over a
fictional payment-support knowledge base (Meridian Switchworks). It is developed separately from the system under test and
reaches it only through an adapter. The design is the
[research protocol v1.0](docs/vision/palladion_retrieval_benchmark_research_protocol.md); its hypotheses H1–H8 are
**unmeasured**.

**Current state:** the development suite (B00), the harness foundation (B01), the synthetic S-tier fixture (B02), the scorers (B03) and the Track A machinery (B04) exist. The harness has typed contracts, strict
configuration, an arm registry, run manifests, a paired runner, a CLI, a secret scanner and a generator pool over three Groq
models. The S-tier fixture (1,200 fictional documents, 100 pilot questions, `scripts/generate_data.py`, `docs/dataset_card.md`) is built; its label audit is done (made by the coordinator under the owner's delegation, with one non-independent reader; see the dataset card). The scorers (`benchmark/eval/`, `benchmark/analysis/`) are proven against perfect, empty and shuffled control arms. R0 to R3 and an HTTP-only adapter for Palladion run end to end through the real runner and validator, but the exploratory pilot has been run on the smoke split (E-B04-005; it supports no ranking claim and the owner can relabel the audit with [the labelling guide](docs/development/OWNER_LABELLING_GUIDE.md)), and there is no confirmatory result yet; hypotheses H1–H8 remain untested. See
[progress](docs/development/PROGRESS.md).

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

## Limits

All data will be fictional and synthetic and is not an actual operating procedure. Synthetic worlds can be easier than real
knowledge, the author of the benchmark also builds Palladion, and a single-provider generator is a confound; the plan records
each as a risk with a mitigation owner.
