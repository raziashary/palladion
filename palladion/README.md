# Palladion system prototype

P01 foundations and P02 ingestion/retrieval have real consumers: strict contracts,
transactional SQLite, immutable originals, dense/BM25 Qdrant search and authenticated
source/search/citation endpoints. P02 phase verification and audit resolution passed; no message API,
agent loop, policy execution or generated-answer result is claimed.

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

## Docker-free Qdrant and retrieval API

On this Windows machine use the installed WSL Ubuntu distribution. From this app directory:

```powershell
uv run --locked --no-env-file python scripts/qdrant_server.py --wsl
```

This verifies the official Qdrant 1.19.2 static release checksum and runs it on
127.0.0.1:16333 (gRPC 16334), with telemetry disabled. Persistent data is stored inside
Ubuntu at `~/.local/share/palladion/qdrant/`, not on the Windows-mounted filesystem.
No Docker installation or system-wide package change is needed. The native Windows
server produced filesystem access errors in this machine's probe; use the WSL path.
Stop with Ctrl+C or the same command plus `--stop` in another terminal. Stop preserves
storage; never delete/reset an existing store for a test. Compose is optional for machines
with working Docker and must not bind the same port concurrently.

In another terminal from this directory:

```powershell
uv run --locked --no-env-file python scripts/seed.py
uv run --locked --no-env-file python scripts/reconcile.py
uv run --locked --no-env-file python scripts/serve.py
```

Seed is idempotent and never restores revoked grants or approvals. Synthetic opaque
bearer tokens are provisioned in ignored `runtime/demo/demo_auth.json`; read only that
explicitly local test file when making requests. Tokens map to stored profiles; a principal
ID in a request or bearer header does not authenticate that identity. This is synthetic
authentication, not enterprise identity integration.

The API listens on localhost:18080: GET `/health/live`, GET `/health/ready`, POST
`/sources`, POST `/sources/{revision_id}/approve`, POST `/sources/{revision_id}/revoke`,
POST `/search`, GET `/evidence/{chunk_id}?case_id=...`, GET `/index-health?case_id=...`.
Upload and approval require separate actors. Approval may provide a same-family scoped
`supersedes_revision_id`. Search and citations recheck stored access, source approval,
applicability and generation. No endpoint generates answers or calls a model provider.

Explicit real-server test and retrieval-only pilot commands:

```powershell
$env:PALLADION_TEST_QDRANT_URL = 'http://127.0.0.1:16333'
uv run --locked --no-env-file pytest
Remove-Item Env:PALLADION_TEST_QDRANT_URL
uv run --locked --no-env-file python scripts/evaluate.py --run
```

Integration tests/evaluation use newly named synthetic collections and temporary SQLite,
then clean their own state. Without the explicit URL, real-server tests are SKIPPED,
never PASS. Reports under ignored runtime/evaluation compare retrieval substrates,
not full B0/B1/B2 answer systems. Pilot labels lack human adjudication. English sources
with English/Indonesian queries do not prove general multilingual quality. Tiny corpora
do not establish HNSW capacity; retain the recorded index-state evidence.
