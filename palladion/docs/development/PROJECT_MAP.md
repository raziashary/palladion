# Project map

Verified 2026-10-17. **Actual documentation is distinct from planned runtime components.**
Source: blueprint “Concrete prototype repository,” “Directory responsibilities,” and “System
architecture.” No diagram node below implies shipped code.

## Actual repository

```text
C:/palladion/                         Git root, main; initial revision 9b167a2
  AGENTS.md                          Project entry instructions
  README.md                          Project introduction and navigation
  .env                               User-supplied ignored credential file; not read/copied
  .gitignore                         Owner-provided .env/.venv exclusions, published unchanged
  baseline/                          Existing empty directory; reserved, not tracked as a directory
  palladion/
    .venv/                           Reused ignored environment; locked P01 dependencies verified
    pyproject.toml, uv.lock          Package metadata and locked dependencies
    README.md, .gitignore            Runnable foundation instructions and local exclusions
    .env.example                     Non-secret future command enablement template
    config/                          Typed settings and fictional policy fixture
    data/demo/                       Four originals, synthetic case/observation/gold catalog
    src/evidence_agent/              core/, security/access, storage/, settings, version
    scripts/validate_foundation.py    Offline actual-domain consumer smoke
    tests/                           Contract, fixture, settings, access and persistence checks
    docs/
      README.md                      Documentation index
      vision/
        palladion-blueprint-v2.md     User's unchanged master vision
      development/                   One canonical agent working-document folder
        MASTER_DEV_PLAN.md           Task protocol, packages, atomic file-specific cards
        GOAL.md                      Checkable outcomes
        ADR_LOG.md                   Structured questions/recommendations/editable owner answers
        TESTING_GATES.md             Proof obligations
        RESEARCH_PROTOCOL.md         Experiments and honest comparison rules
        REQUIREMENTS_TRACEABILITY.md Blueprint/user requirement coverage
        PROJECT_MEMORY.md            Single compact recovery record
        PROJECT_MAP.md               This map
        PROJECT_LEARNING.md          Lessons and corrections
        PROGRESS.md                  Task/gate states
        RISKS_AND_OPEN_QUESTIONS.md   Accepted directions, pending evidence and deferred scope
        EVIDENCE_LOG.md              Verification records
        check_docs.py               Links/IDs, atomic metadata/dependencies, planned-file coverage
```

## Ingestion/retrieval now implemented (P02, verified with audit resolution)

`ingest/` parses original spans, chunks structural context and stages exact generations.
`storage/catalog.py` owns additive v3 chunks/manifests/aliases/context links. The real
Qdrant adapter stores named neural dense/native BM25 points; `retrieval/` canonicalizes
ACL/approval/time/generation and supports bounded learned rerank/context expansion.
`api/` and main factory expose authenticated source/search/citations; telemetry has an
internal correlated reader. Seed/reconcile/serve/evaluate scripts use those actual owners.
WSL standalone launcher verifies Qdrant release hashes and preserves Linux-owned storage.
Compose is optional. P03 now implements the policy/live domain path below; message/LLM/critic/graph runtime remains future.

## Foundation now implemented (P01)

The app package/uv.lock/settings, core models/errors/IDs/fixtures, security access,
SQLite schema/migrations/registry/originals, synthetic data/policy, tests and offline
scripts/validate_foundation.py now exist. Offline flow: typed fixtures → trusted bootstrap
profiles/memberships → Registry upload/independent approval → OriginalStore exact bytes →
close/reopen Database → current stored ACL and approved-source reader → byte/range proof.
CLI state is temporary and cleaned; no API/search/provider process is started.

## Runtime ownership and later planned components

Paths are relative to `palladion/`; P01/P02 and the P03 domain path are implemented; later agent/gate/memory/critic/graph components remain planned. ADR-0001 maps the
blueprint's illustrative `evidence-agent/` root here; do not create a duplicate project.

| Planned area | Owns | Producers / consumers | Build phase |
|---|---|---|---|
| `pyproject.toml`, `uv.lock`, config, compose | uv-managed app environment, pins, flags/budgets and local services | Settings → application and evaluator | P01/P02 |
| `src/evidence_agent/core/` | Versioned typed contracts, IDs and errors | All modules share these; no storage→agent dependency | P01 |
| `security/access.py` | Principal authentication and tenant/case/role/source permissions | Request context → every domain/source boundary | P01 onward |
| `storage/` and immutable originals | SQLite registry/schema/exact IDs, source bytes, Qdrant/Neo4j adapters | Ingest writes; resolver and domain readers consume | P01/P02/P07 |
| `ingest/` | Parse/chunk metadata, staged generations, reconciliation, optional graph extraction | Accepted original → derived stores → publish marker | P02/P07 |
| `retrieval/` | Dense/BM25/exact fusion, rerank/context, canonical evidence, required slots | Index candidate IDs → authorized original spans/ledger | P02 |
| `policy/` | Approved rule discovery, temporal version selection, bounded typed AST | Source clauses + trusted facts → decision trace | P03 |
| `live/` | Named allowlisted read-only operations, target auth, timestamps/freshness | Mock owned observations → ledger/policy facts | P03 |
| `agent/` | Preflight, four tool facades, bounded loop, draft, critic, final gate | Domain evidence → qualified claims and disposition | P04/P06 |
| `memory/` | Scoped events/facts, FTS recall, generated packet, scoped hot cache | Validated events → next authorized request | P04 skeleton/P05 |
| `graph/` | Verified/provisional identity and typed source-backed relationships | Reviewed source extraction → optional bounded discovery | P07 |
| `api/`, `main.py` | Transport, app wiring, auth boundary, messages/evidence/timeline/trace/health | Operator request → runtime; citations → source reader | P02/P04 |
| `telemetry/audit.py` | Redacted correlated trace, counters and cost/failure data | Every runtime stage → evaluator/debug authorized reader | First runtime slice onward |
| `data/demo/`, `tests/`, `scripts/` | Synthetic fixtures, gates, evaluation/reconciliation | Known expected evidence → actual run artifacts → scorer | P01 onward |

Do not create all 74 proposed files as empty placeholders. Check named APIs/dependencies
at implementation time. No frontend, autonomous financial actions, event broker or extra
agent role is required by the prototype.

Current owner choices: uv venv lives inside `C:/palladion/palladion`; later baseline
dependencies are isolated. Main/critic initial runtime uses actual Groq
`qwen/qwen3.8-27b`, independent contexts with shared model, not independent ground truth.
Root `.env` is loaded only for an explicitly enabled future provider command. P01 package
setup is authorized and verified; model integration remains P04 work. The user-created `.venv` now exists and is ignored. Manifest/lock and P01 foundation now exist; retrieval/agent runtime remains planned.
P01 package installation succeeded in the existing environment; no provider call occurred.

## Planned request and evidence flow

```mermaid
flowchart TD
  API[Authenticated FastAPI request] --> PRE[Nonexclusive preflight and case packet]
  PRE --> MAIN[Bounded main agent]
  MAIN --> TOOLS[Four read tools]
  TOOLS --> SEARCH[Hybrid retrieval and optional graph]
  SEARCH --> RESOLVE[Canonical source resolver with ACL and time]
  TOOLS --> POLICY[Deterministic policy and time resolver]
  TOOLS --> LIVE[Scoped mock live observations]
  TOOLS --> MEM[Attributed scoped recall]
  RESOLVE --> LEDGER[Evidence ledger]
  POLICY --> LEDGER
  LIVE --> LEDGER
  MEM --> LEDGER
  LEDGER --> DRAFT[Atomic draft claims]
  DRAFT --> CRITIC[Advisory critic and bounded counter-search]
  CRITIC --> FINAL[Reserved main finalization]
  FINAL --> GATE[Deterministic evidence gate]
  LEDGER --> GATE
  GATE --> ANSWER[Five dispositions and resolvable citations]
  GATE --> EVENTS[Validated events and packet regeneration]
  EVENTS --> PRE
```

The renderer uses safe templates if budget/model output fails. Identity never comes from
tool arguments or packet text. Both retrieval and graph resolve to original authorized
spans; neither graph connectivity nor score creates policy authority. The gate owns release,
but it is not a complete natural-language theorem prover.

## Planned ingestion and future evaluation flow

Immutable bytes + authenticated metadata → registry → structural chunks with exact spans →
hidden dense/BM25/exact and optional graph generation → manifests/reconciliation → atomic
SQLite publication marker → canonical resolver → citation GET. Revocation acts in SQLite
immediately; asynchronous index/cache cleanup cannot be the access-control boundary.

Future `baseline/` systems → shared evaluation contract ← Palladion arms → frozen corpus,
gold labels and scorer → report with raw safety/usefulness/latency/cost dimensions. All
comparison adapters and results are currently absent; see RESEARCH_PROTOCOL and X01.

Dependency manifest ownership is checked by scripts/check_dependencies.py over src/scripts/tests (including literal dynamic imports); pyproject runtime/dev declarations and uv.lock own dependency setup. E-P02-002 records the follow-up completion checks.

## P03 domain path (implemented and phase-reviewed)

Authenticated source-linked policy approval → policy_versions/source clauses plus append-only approval/revocation/supersession events → temporal resolver. Admin-registered case scope → named target-authorized mock gateway → minimized persisted LiveObservation events → PolicyEngine evidence-ID reader → normalized safe AST execution → persisted PolicyDecision → reopened replay/source reader. Policy/live modules share existing SQLite, original bytes and access checks; schema remains v3. scripts/validate_policy.py exercises the real path without Qdrant/network/provider. P04 owns gate/tool/API integration.
