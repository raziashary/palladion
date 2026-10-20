# Palladion application

P01–P05 have completed phase-local implementation and independent review: canonical
sources and contracts, dense/BM25 retrieval, temporal policy execution, bounded Groq
messages and scoped continuity. P06 adds independent advisory review, bounded
counter-search and reserved finalization; its phase-local implementation, validation and independent audit are complete. Actual provider failures and mechanical pilot limits remain visible in the
development evidence; these checkpoints do not establish production readiness or
semantic accuracy.

P07 phase-local implementation and review are complete: optional source-linked graph,
backend sessions and automatic memory promotion have actual reader/provider proof.
The paired graph pilot added zero recoveries, so graph stays off by default. Semantic
memory classification accuracy remains unadjudicated.

P08's engineering pilot is complete: isolated B0–B9/vector controls, bounded optional
planner/adaptive review, sqlite-vec derived memory and saved-output scoring are verified.
Ordinary serving retains mandatory review, four read tools and canonical authorization.
The owner-approved grid recorded 44 observations, including 16 row-level errors.
The historical24mapped integrity checks passed; P09 reaudit found missing complete
T01/T12 consumer scenarios and added them separately. Historical review receipts remain evidence,
not a guarantee that subsequent audits find no defects.
Failures, omissions, unknown semantic accuracy and unavailable higher-stage retrieval
metrics remain explicit. See the [pilot report](docs/development/evidence/P08_RESULTS.md).

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
disabled. The actual key stays only in the ignored repository-root `../.env`. An
explicitly enabled command loads that file and checks access/quotas; key existence
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

P01–P06 implement canonical sources, retrieval, temporal policy execution, mock observations,
bounded tools/agent/release gate, scoped continuity and advisory critique. P07 graph and
automatic memory consumers have completed phase-local verification and independent review.
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
search cancellation are verified. Single end review and finding resolution are complete. P05 adds scoped continuity;
critic is implemented in P06. Five dispositions and document citation paths have actual
provider proofs, with every model/quota/schema failure retained (E-P04-001).
Two final no-evidence refreshes failed strict assertions while safely abstaining;
these engineering path checks do not establish model reliability. P05 is published; P06 is published and verified complete.
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


## Scoped continuity (P05)

P05 phase-local implementation and single audit/resolution are verified complete. Scoped episodic/semantic/procedural
memory uses current persisted permissions: USER owner, CASE members, explicit TEAM
members, and administrator-promoted ORGANIZATION items. Case-derived sharing retains
its origin-case/source restrictions. All remembered assertions remain context; they
cannot become company policy or authorize actions. Only owner/authorized administrator
operations change validity, corrections or revocation. Unspecified expiry stays
UNSPECIFIED; old live observations always require a new read for current decisions.

The four-tool recall handler accepts optional query, memory_id and category selectors;
default limit/event behavior remains compatible. Packets preserve unresolved slots,
reported facts, hypotheses and historical observations with recheck labels. Exact
passage cache hits always validate current source state; no speed claim is made.
Schema v4 upgrades preserve old rows and first create a checked .pre-v4-UUID.sqlite
backup alongside any recognized persistent database. Foreign schemas fail closed.
No task migrated the user's demo store. Retain backups; do not delete runtime data.

Trusted local synthetic operator example (requires filesystem access, not an HTTP or
multiuser authentication boundary): `python scripts/memory.py --root runtime/demo
--principal reader-a --case case-42 recall --query debit`. Actions write/correct use a
bounded MemorySpec JSON --spec file; revoke uses --id; administrator team-add/team-revoke
use --team/--member; close invalidates case continuity. No such writes are LLM tools.

Explicit real-provider pilot: `python scripts/evaluate.py --run --memory
--enable-live-llm --model openai/gpt-oss-120b`. It uses temporary synthetic stores and
its own UUID collection, and records all B4/B5/compressed outputs, usage and failures.
The current pilot retained the critical gap in B5 packets, but strict completion was
0/3 due model/tool errors. This establishes measurements, not a memory-improvement or
reliability claim. See E-P05-001. Critic integration is verified in P06; confirmatory scientific evaluation remains deferred beyond the completed P08 pilot.

Final P05 evidence: E-P05-001,246source+12actual-Qdrant checks, updated wheel and single audit resolution. Recall applies current scope before its bounded window and reports non-exhaustive coverage. P06 is published and verified complete; pilot0/3 strict completions remain disclosed.

## Independent evidence review (P06)

The runtime drafts with four read tools, sends a fresh question/evidence/draft context
to an advisory critic, executes only backend-scoped knowledge counter-searches, and
uses one reserved main call to finalize. The deterministic gate re-reads canonical
sources before release. Critic PASS never grants authority or clears missing policy
inputs; consequential guidance remains qualified under the synthetic pilot boundary.

Limits are five main calls including finalization, three critic calls, two critic
searches within eight total tools, and the configured request deadline. Message and
redacted timeline readers expose review status and consumed counts, never raw reviews.
The isolated critic-off experiment does not disable mandatory review in the runtime.

Run the controlled measurement explicitly, using an owner-approved model:

```powershell
uv run --locked --no-env-file python scripts/evaluate.py --run --critic --enable-live-llm --model openai/gpt-oss-20b
```

Every condition and failure is retained. Equal saved initial hashes support paired
comparison; synthetic draft errors and exact quote checks are mechanical controls,
not human-adjudicated semantic accuracy. See E-P06-001 and ADR0046/0049/0050.

P06 verification:307disjoint source/integration checks, installed-wheel checks, real Groq
normal and exact-recovery paths, and sole independent audit/resolution (E-P06-002).
A changed final proposal or unresolved advisory challenge qualifies the answer while
canonical facts remain visible. The16-condition frozen pilot retained all known facts,
but full exception correction was0/4 and one critic validation failed; this is not a
reliability or hypothesis-success claim. The draft-blind experimental first pass still
receives canonical policy-required slots. P07 is verified within its phase-local boundary; P08 semantic accuracy remains unknown without independent human adjudication.

## Optional graph and automatic memory (P07)

Neo4j is a derived navigation index; SQLite and immutable original spans remain canonical.
Verified identities, provisional source mentions, relation reviews and accepted/rejected
merges retain provenance. Traversal rechecks current source access, generation and bytes;
paths cannot authorize a claim. Graph is off by default. The small paired development
pilot found zero incremental exception recoveries over B2 and retained all degradation.

Docker-free local setup uses a pinned Neo4j Community archive and portable Java21 in
WSL-owned `~/.local/share/palladion/neo4j-p07/`. The approved synthetic setup disables
database auth and HTTP, exposing only loopback Bolt17687. Do not use it with real data.

```powershell
uv run --locked --no-env-file python scripts/neo4j_server.py --wsl
uv run --locked --no-env-file python scripts/seed.py --enable-graph
uv run --locked --no-env-file python scripts/reconcile.py --enable-graph
uv run --locked --no-env-file python scripts/serve.py --enable-graph --enable-live-llm
```

Stop the owned graph process with the launcher plus `--stop`; data is preserved.
`--require-graph` makes unavailable relation verification explicit rather than silently
using graph-off behavior. Qdrant must also be running. These commands are opt-in; the
recorded pilot does not justify enabling graph by default. Seed, reconcile and serve
accept matching `--graph-partition` and `--graph-timeout` settings; defaults remain
partition `palladion_graph_v1`, timeout2seconds. The positive consumer pilot explicitly used
10seconds; seed transaction timeouts at that cap remain recorded failures.

The backend automatically categorizes bounded chunks after persisting request/tool/release
events. Path A uses deterministic rules: explicit personal preferences become private USER
semantic memory, observed allowlisted tool experience becomes unapproved procedural
context, and remaining/uncertain chunks stay episodic. Original event IDs, UTF-8 offsets,
hashes and classification decisions are persisted atomically. Failed promotion preserves
the original event and records a diagnostic.

Messages accept an optional `session_id` and return the resolved ID. Omitting it reuses
the owner's active case session. `POST /v1/cases/{case_id}/sessions` starts a new session;
`POST /v1/cases/{case_id}/sessions/{session_id}/close` closes an owned session. Episodic
model recall is session-local. Preferences can cross sessions for the same user while
retaining original case access. Redacted canonical case audits remain separate.

Path B is an additional explicitly enabled local job, using the existing pinned encoder:

```powershell
uv run --locked --no-env-file python scripts/promote_memory.py --enable-path-b --root runtime/demo --principal reader-a --case case-42 --session SESSION_ID --event EVENT_ID
```

It has a 30-second process deadline and at most eight events/64 chunks, makes no Groq
calls, and records cosine scores plus margin loss. Rules retain weight0.8 and hard
boundaries cannot be overridden. Uncertain scores abstain. Defaults are frozen pilot
settings, not trained or calibrated accuracy. Models still have only four read tools;
procedural experience never becomes approved policy or executable instructions.

## Search and administrative contracts

`POST /search` accepts case_id, query, mode, limit (default12, maximum40), optional
`as_of` and optional `token_budget`. The model's search tool remains capped12.
`as_of` must include a timezone and selects document applicability only; it cannot
supply trusted transaction time or restore revoked approval, membership or source ACL.
Use the same cutoff with `GET /evidence/{chunk_id}?case_id=...&as_of=...` for historical
original-byte readback. Defaults continue to select current applicable sources.

`token_budget` keeps a ranked prefix of complete passages. It never truncates canonical
text or changes spans/hashes. Response evidence_budget records requested/returned counts,
used/limit tokens, separator and pinned retrieval-tokenizer identity. These counts are
not Groq tokens or billing estimates. Without a budget, this tokenizer path is not loaded.
Token-budget requests use local files only; provision the pinned cache through the
explicit seed/probe setup first. A missing or malformed local tokenizer returns503.
Approval automatically registers bounded family/revision/identifier aliases for HTTP
uploads. The exact discovery lane reads at most100candidates plus a sentinel and
reports EXACT_CANDIDATES_TRUNCATED when bounded; current ACLs filter before that cap.
An unknown structured identifier still cannot silently return a near identifier.

Physical coverage checks use batches of at most64generations, with full vector/hash/
fingerprint reconciliation by default. They inspect up to10000authorized source
rows; source_counts_complete=false explicitly marks a larger truncated scope. The adapter
bounds each physical batch and the aggregate coverage result at100000points; canonical
manifest loading also streams at most100000rows. Overflow yields explicit
COVERAGE_POINT_LIMIT or CANONICAL_MANIFEST_UNAVAILABLE degradation. It rejects repeated
pagination offsets. A
healthy larger corpus is not degraded merely for exceeding100sources. Coverage remains
linear work and does not attest an external source inventory.

Current tenant admins with document:approve may use `POST /v1/admin/principals`,
`POST /v1/admin/cases`, and `POST /v1/admin/cases/{case_id}/memberships`. Principals
receive only the non-admin reader role and approved grants bounded by the issuer's.
The submitted `principal_id` is a tenant-local subject key. Store the returned opaque
canonical `principal_id` and use it for memberships, source ACLs and operator token
mappings; the same key in another tenant yields a different canonical identity.
Membership writes require current admin membership in the case; current source ACLs
remain independent. Repeated create requests never restore revoked access. These APIs
create no tenants, admin roles or bearer tokens; opaque authentication mappings remain
operator-provisioned. They are synthetic research administration, not enterprise IAM.

`python scripts/evaluate.py --capabilities` inspects the supported isolated study arms
without credentials, services or generation. Unsupported integrity-bypass ablations are
explicitly FEATURE_NOT_SUPPORTED. Ordinary serving retains deterministic preflight,
canonical authorization/time/parser boundaries and the final gate. Future study execution
is owned by a cancellable process tree; partial attempts and unknown usage survive a
whole-run deadline. Consumed config/fixture bytes are copied into and read from the bound
run inputs. Legacy P08 configuration and completeness-metric limits are recorded in the
[pilot report](docs/development/evidence/P08_RESULTS.md), without rewriting its raw run.


Physical audit reuse is experimental and explicitly enabled per request with
`reuse_physical_audit: true` on `POST /search`, or the same query parameter on
`GET /index-health`. Default requests and the four domain tools remain fresh. Only a
complete healthy physical audit may be reused, for at most five seconds from its
original start; hits do not renew that age. Current principal/case/source ACL, approval,
validity, generation and exact canonical manifests are rechecked on every request.
Responses expose `physical_audit_mode`, `physical_verified_at` and
`physical_cache_status`. A cached physical success can miss out-of-band index corruption
within that disclosed window; a failed fresh audit attempts to invalidate prior cached
successes. The bounded derived sidecar stores only keys/timestamps (32 entries, 1 MiB),
not evidence text. Cache errors fall back to fresh checks. Small workloads and cold
misses may pay extra overhead; PF03 performance acceptance remains open pending the
retained comparison. This status does not weaken citation or final-gate validation.
