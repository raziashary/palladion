# Palladion benchmark

**A controlled experiment on whether evidence-first retrieval and answering is measurably more reliable than
standard and strong RAG baselines.**

This folder holds the benchmark for [Palladion](../palladion/README.md): a retrieval and evidence-reliability study over a
fictional payment-support knowledge base (Meridian Switchworks). It is developed separately from the system under test and
reaches it only through an adapter. The design is the
[research protocol v1.0](docs/vision/palladion_retrieval_benchmark_research_protocol.md); its hypotheses H1–H8 are
**unmeasured**.

**Current state:** development suite only (phase B00). There is no benchmark code, dataset, adapter, provider call or
result yet. The only gate run so far is the documentation checker. See [progress](docs/development/PROGRESS.md).

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
uv run pytest
```

No runtime dependencies are declared yet; dependencies are added by the task that needs them. Provider calls are disabled
until the owner provisions credentials and enables them explicitly (see [open questions](docs/development/RISKS_AND_OPEN_QUESTIONS.md)).

## Limits

All data will be fictional and synthetic and is not an actual operating procedure. Synthetic worlds can be easier than real
knowledge, the author of the benchmark also builds Palladion, and a single-provider generator is a confound; the plan records
each as a risk with a mitigation owner.
