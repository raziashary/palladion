# Palladion application

P01 foundations and P02 ingestion/retrieval have real consumers: strict contracts,
transactional SQLite, immutable originals, dense/BM25 Qdrant search and authenticated
source/search/citation endpoints. P02 phase verification and audit resolution passed. P04 now has a message API,
main loop and gate under verification; selected real Groq outputs are recorded, not phase completion. P03 now adds approved temporal policy
execution and read-only mock operational observations; phase-local validation and single work review are complete (E-P03-001).

Phase ownership and evidence are in the [development plan](docs/development/MASTER_DEV_PLAN.md)
and [current progress](docs/development/PROGRESS.md).

See the [repository overview](../README.md) for the motivation and system architecture.
This directory owns the Python implementation, configuration, fictional corpus, scripts
and tests. SQLite/originals own source authority; Qdrant supplies discovery candidates.
Approval and index readiness are separate states, and citation text comes from original
bytes after current authorization and publication checks.

## Prerequisites and setup

Install uv and a compatible Python. The tested interpreter is Python 3.14.7; the package
declares Python 3.11–3.14, but this checkpoint has not verified the other versions.
Real retrieval needs local Qdrant. The standalone launcher supports x86_64 Linux and
uses an installed WSL Ubuntu distribution with Python 3 on Windows. Initial dependency,
server and model installation needs network access; inference runs locally.

From this directory, use the existing `.venv` and the committed dependency lock:

```powershell
uv sync --locked
uv run --locked --no-env-file python -c "import evidence_agent; print(evidence_agent.__version__)"
uv run --locked --no-env-file python scripts/check_dependencies.py --self-test
uv run --locked --no-env-file pytest
uv run --locked --no-env-file ruff check .
uv run --locked --no-env-file mypy src scripts
uv run --locked --no-env-file python -m build --installer uv
uv run --locked --no-env-file python scripts/validate_foundation.py
```

The offline foundation command validates all 24 fixture cases and uses temporary local
stores to exercise the production registry/access/original-byte methods, including
close/reopen and forbidden reads. It starts no server and never loads credentials.
Gold annotations are pilot fixtures, not independently adjudicated research truth.

`pyproject.toml` declares direct dependencies; `uv.lock` records their complete resolution.
The import/manifest checker includes literal dynamic imports and rejects reliance on a
package being installed only transitively. `SearchIndex` and `DenseEncoder` are Python
`Protocol` interfaces: their ellipsis bodies specify contracts. `QdrantIndex` and
`FastEmbedDenseEncoder` contain the concrete implementations.

If the environment is absent, first verify `.venv/` is ignored, then run `uv venv` and
`uv sync --locked`. Do not recreate an existing compatible environment. Python 3.11–3.14
is declared; executed compatibility evidence identifies the actual tested interpreter.

`config/settings.yaml` selects Groq `qwen/qwen3.8-27b`, with live generation explicitly
disabled. The actual key stays only in the ignored repository-root `../.env`. A later
P04 enabled command will explicitly load that file and check access/quotas; key existence
alone does not permit dispatch. Current retrieval makes no generative-provider or operational-service request.

All business documents/data are fictional. Approval comes from stored authenticated
synthetic administrator events, never wording inside a document. Model/packet identity
cannot replace backend principal context. No payment actions are available.

Run destructive migration tests only against their generated temporary resources.
Never point tests at an existing database or delete persistent resources without the
required backup/approval. Existing `.env`, `.venv`, database files and build artifacts
are ignored; `baseline/` remains reserved for later comparisons.

## Docker-free Qdrant and retrieval API

On Windows, use an installed WSL Ubuntu distribution. From this app directory:

```powershell
uv run --locked --no-env-file python scripts/qdrant_server.py --wsl
```

This verifies the official Qdrant 1.19.2 static release checksum and runs it on
127.0.0.1:16333 (gRPC 16334), with telemetry disabled. Persistent data is stored inside
Ubuntu at `~/.local/share/palladion/qdrant/`, not on the Windows-mounted filesystem.
No Docker installation or system-wide package change is needed. The native Windows
server produced filesystem access errors during verification; use the WSL path.
Stop with Ctrl+C or the same command plus `--stop` in another terminal. Stop preserves
storage; never delete/reset an existing store for a test. Compose is optional for machines
with working Docker and must not bind the same port concurrently.

On x86_64 Linux, run the same launcher command without `--wsl`. HTTP uses port16333 and
gRPC uses16334 by default. Stop preserves the Linux-owned persistent store.

## Seed, reconcile and serve

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

Reconciliation checks the active generation's exact IDs, hashes and representation
fingerprint. A mismatch exits unsuccessfully; it does not silently repair or delete data.

The API listens on localhost:18080: GET `/health/live`, GET `/health/ready`, POST
`/sources`, POST `/sources/{revision_id}/approve`, POST `/sources/{revision_id}/revoke`,
POST `/search`, GET `/evidence/{chunk_id}?case_id=...`, GET `/index-health?case_id=...`.
Upload and approval require separate actors. Approval may provide a same-family scoped
`supersedes_revision_id`. Search and citations recheck stored access, source approval,
applicability and generation. These unversioned source/retrieval endpoints make no
provider calls; the explicitly enabled versioned message endpoint below runs the agent.

| Method | Route | Purpose |
|---|---|---|
| GET | `/health/live` or `/health` | Application liveness |
| GET | `/health/ready` or `/ready` | SQLite, Qdrant and explicit model-boundary readiness; no provider probe |
| POST | `/sources` | Bounded Markdown/plain-text upload and metadata |
| POST | `/sources/{revision_id}/approve` | Independent approval and indexing |
| POST | `/sources/{revision_id}/revoke` | Immediate source authority revocation |
| POST | `/search` | Authorized passages, citations and coverage warnings |
| GET | `/evidence/{chunk_id}?case_id=...` | Original-byte citation readback |
| GET | `/index-health?case_id=...` | Authorized supplied-source index coverage |
| POST | `/v1/cases/{case_id}/messages` | Current case member: bounded investigation and qualified claims/citations |
| GET | `/v1/evidence/{evidence_id}?case_id=...` | Current canonical document/live/policy/event evidence reader |
| GET | `/v1/evidence/{evidence_id}/clauses/{clause_index}?version_id=...&case_id=...` | Exact approved policy clause bytes referenced by that decision |
| GET | `/v1/cases/{case_id}/timeline` | Current case member: recent redacted runtime event metadata |
| GET | `/v1/traces/{trace_id}?case_id=...` | Current admin AND current case member: bounded redacted developer diagnostics |

Management, search and citation routes require `Authorization: Bearer <local-token>`.
For a seeded case, the search JSON body is:

```json
{"case_id":"case-42","query":"settlement reversal investigation","mode":"hybrid","limit":12}
```

Search modes are `lexical`, `dense`, `hybrid` and `reranked`. Start the API with
`scripts/serve.py --rerank` to enable its optional local cross-encoder. Discovery and
reranking have explicit candidate budgets; returned passages are capped at12. Expected
reranker failures produce a degraded result with warnings. Index coverage, external
inventory attestation and answer sufficiency remain separate concepts.

## Real-server validation and retrieval pilot

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

Reports preserve immutable run IDs, model/index fingerprints, raw stage ranks, failure
records and metrics for dense ANN/exact, lexical, hybrid, exact-ID union, reranking and
expansion. English and no-stemming BM25 profiles are measured separately. These are
retrieval substrate comparisons; full answer arms and held-out evaluation remain later work.

## Development boundary

P03 implements temporal policy execution and mock observations under explicit GO. Later phases
cover bounded tools/agent/release gate, continuity, critic and optional graph experiments.
No provider key is needed for the implemented retrieval slice. Keep live credentials out
of verification commands and stop any test servers you start. See
[testing gates](docs/development/TESTING_GATES.md) and
[evidence](docs/development/EVIDENCE_LOG.md) for the verified boundary and remaining work.

## Temporal policies and mock observations

Run the isolated P03 domain demonstration without Qdrant, provider keys or network calls:

```powershell
uv run --locked --no-env-file python scripts/validate_policy.py
```

It creates fictional source/approval records, registers source-linked decision tables,
reads target-authorized mock observations, executes a bounded safe predicate AST and
reopens SQLite to replay the resulting trace. The same transaction can select the 2025
transaction-time rule while current handling selects a separate 2026 handling family.
Missing settlement stays `INCOMPLETE_INPUT`; an `OK` read never authorizes a payment action.

Policies declare one of four trusted time bases: transaction event, canonical case opening,
backend evaluation clock or a named authenticated domain event. Selection uses half-open
valid intervals, registry knowledge cutoffs and explicit scoped supersession. Overlapping
incomparable policies or undefined mixed bases remain conflicts. Historical audit mode is
explicitly administrator-only and distinct from current operational guidance.

`live/` provides transaction, settlement, incident and optional merchant-summary mock reads.
`config/adapters.yaml` records fictional owner-defined timeouts, freshness, response and
concurrency limits. Fresh read time cannot refresh an old BI `data_as_of` cutoff. The gateway
accepts no URL, SQL, write verb, credentials or caller-chosen principal. Policy inputs are
resolved from persisted observation IDs; a caller-supplied verified label is not evidence.

Decision traces retain normalized inputs, source spans, selected version/time, row results
and outcome. The replay reader rechecks access and source eligibility and recomputes matched
rows. A stored decision is an audit artifact, not fresh permission to act. This is a direct
domain interface is consumed by P04 tool facades, policy HTTP/messages and final gate.
No real enterprise connector or generated-answer research benchmark is included.

P04 implementation and phase-local checks now cover real Groq transport, bounded loop,
four scoped tools, request ledger, necessary-condition gate and message/timeline/citation
readers. Scoped admin developer traces, dependency/config readiness and owned-process
search cancellation are verified. Single end review and finding resolution are complete; full memory and
critic remain later phases. Five dispositions and document citation paths have actual
provider proofs, with every model/quota/schema failure retained (E-P04-001).
Two final no-evidence refreshes failed strict assertions while safely abstaining;
these engineering path checks do not establish model reliability. P05 requires GO.
Use `python scripts/seed.py --policies` to explicitly seed trusted synthetic case/policy
fixtures. After setup, `python scripts/serve.py --enable-live-llm` explicitly enables
root .env credential loading and real model calls; omitting the flag disables messages.
Actual-provider smoke: `python scripts/validate_agent.py --enable-live-llm --scenario supported`.
Other scenarios are document/partial/conflict/no_evidence/unavailable; engineering checks
are distinct from model-quality research. See E-P04-001 for passing and failed probes.


The live server and walkthrough CLI accept explicit `--model qwen/qwen3.8-27b`,
`--model openai/gpt-oss-120b` or `--model openai/gpt-oss-20b`. Qwen remains the default.
All three run through Groq with the same four local read tools and release checks;
no built-in web/code tools or automatic model fallback are enabled. Enablement still
requires `--enable-live-llm`. CLI output names the actual model and includes bounded
rate-limit headers (request counters are per day, token counters per minute).

API route docstrings in `src/evidence_agent/api/routes.py` describe each endpoint's
purpose, current authorization and response/failure behavior, and populate OpenAPI.
The native-tool flow is `agent/llm.py` (transport) → `agent/loop.py` (budgeted native
call handling) → `agent/tools.py:Tools.execute` (validated domain dispatch) → loop
(matching tool-call results) → model → deterministic gate. Models never execute tools
directly or supply their own identity/case authority.
