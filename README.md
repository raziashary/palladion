# Palladion

Palladion is a planned evidence-first agent harness: it protects answer integrity,
recognizes insufficient evidence, preserves case context, and challenges its conclusions.
The initial research domain is internal support investigation using synthetic payment
documents and read-only mock operational systems.

**Current state:** development documentation established; the system is not implemented.
There is no application, UI, dependency manifest, or benchmark result yet.

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
