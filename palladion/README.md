# Palladion foundation

Phase 1 provides strict contracts, synthetic authorization and approval records,
transactional SQLite, immutable source bytes and a pilot fixture catalog. It does not
yet provide retrieval, a message API, the agent loop or policy execution.

Phase ownership and evidence are in the [development plan](docs/development/MASTER_DEV_PLAN.md)
and [current progress](docs/development/PROGRESS.md).

From this directory, use the existing `.venv` and the committed dependency lock:

```powershell
uv sync --locked
uv run --locked --no-env-file python -c "import evidence_agent; print(evidence_agent.__version__)"
uv run --locked --no-env-file pytest
uv run --locked --no-env-file ruff check .
uv run --locked --no-env-file mypy
uv run --locked --no-env-file python -m build
uv run --locked --no-env-file python scripts/validate_foundation.py
```

The offline foundation command validates all 24 fixture cases and uses temporary local
stores to exercise the production registry/access/original-byte methods, including
close/reopen and forbidden reads. It starts no server and never loads credentials.
Gold annotations are pilot fixtures, not independently adjudicated research truth.

If the environment is absent, first verify `.venv/` is ignored, then run `uv venv` and
`uv sync --locked`. Do not recreate an existing compatible environment. Python 3.11–3.14
is declared; executed compatibility evidence identifies the actual tested interpreter.

`config/settings.yaml` selects Groq `qwen/qwen3.8-27b`, with live generation explicitly
disabled. The actual key stays only in the ignored repository-root `../.env`. A later
P04 enabled command will explicitly load that file and check access/quotas; key existence
alone does not permit dispatch. P01 makes no model or operational-service request.

All business documents/data are fictional. Approval comes from stored authenticated
synthetic administrator events, never wording inside a document. Model/packet identity
cannot replace backend principal context. No payment actions are available.

Run destructive migration tests only against their generated temporary resources.
Never point tests at an existing database or delete persistent resources without the
required backup/approval. Existing `.env`, `.venv`, database files and build artifacts
are ignored; `baseline/` remains reserved for later comparisons.
