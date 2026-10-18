# Palladion

Palladion is a planned evidence-first agent harness: it protects answer integrity,
recognizes insufficient evidence, preserves case context, and challenges its conclusions.
The initial research domain is internal support investigation using synthetic payment
documents and read-only mock operational systems.

**Current state:** P01 is verified; P02 provenance retrieval is verified complete: strict
contracts, persisted synthetic access/approval, SQLite/originals and 24 pilot fixtures.
The uv package/lock and offline validation entry point exist. Message API,
agent loop, UI and full answer-system benchmark results remain absent.
P02 includes real dense/BM25 Qdrant retrieval, source/search/citation API and retrieval-only
pilots. Use the Docker-free WSL launcher documented in palladion/README.md.
User selected uv and actual Groq `qwen/qwen3.8-27b` for future implementation. All
recommendation directions are answered in the editable ADR log. The user created the
ignored app `.venv` after separate toolchain repair; product dependency setup and execution
are authorized by the explicit P01 GO. Current evidence is in the development suite;
no provider call is needed for this deterministic phase. P03 remains future scope.

- [Documentation entry point](palladion/docs/README.md)
- [Master vision](palladion/docs/vision/palladion-blueprint-v2.md)
- [Master development plan](palladion/docs/development/MASTER_DEV_PLAN.md)
- [Current progress and next task](palladion/docs/development/PROGRESS.md)
- [Project instructions](AGENTS.md)

`palladion/` owns the system. `baseline/` is reserved for later comparisons with standard
RAG, LangChain RAG, and provider systems. The immediate priority is system behavior and
falsifiable hypothesis testing. UI development is excluded.

Documentation validation (Python standard library only, from repository root):

```powershell
python palladion/docs/development/check_docs.py
python palladion/docs/development/check_docs.py --self-test
```

These commands validate the documentation's structure and references, not system behavior.
