# Testing gates

P01 foundations and P02 ingest/retrieval/API/evaluator checks are runnable. Real-server
checks require explicit local-server enablement. Later agent/graph/full research obligations remain planned. Gate catalog rows
describe full obligations; current phase-local results never imply full runtime proof. Gate states
and evidence are recorded in [PROGRESS](PROGRESS.md) and [EVIDENCE_LOG](EVIDENCE_LOG.md).
Read source and test fixtures before running anything with stateful-resource access.

## Execution and evidence rules

- Derive tests from the blueprint and task contract. Each guard needs a violating case
  that fails and a valid case that passes. Do not merely assert an internal method was called.
- A gate passes only after its named acceptance is observed through its producer and real
  consumer. Unit mocks do not substitute for real Qdrant/Neo4j integration where required.
- Multi-phase gates accumulate evidence. Use PARTIAL with explicit covered/uncovered
  obligations until the whole contract passes. Phase exits require that phase's acceptance
  and tests, not unbuilt later capabilities; an early unit check never closes the full gate.
- Default pure/domain tests use synthetic temporary directories/databases and mock
  operational adapters. Deterministic tests may inject typed inputs, errors or transport
  results to exercise guards; they do not establish runtime model behavior. The user's
  ADR-0013 override requires actual Groq `qwen/qwen3.8-27b` for generative integration,
  with explicit enablement after GO. No fake-first runtime acceptance path.
  Inspect downgrade/drop/truncate/reset/reseed/teardown paths first. No ambient live credentials.
  Persistent Compose volumes are state, not disposable by assumption; backup/approval before destruction.
- Bound and pin tests. No unbounded model spend. Explicit enablement, recorded budget,
  model/config and command are required for live-provider evaluation; credential presence is insufficient.
- Record revision, task/gate, exact command and cwd, environment/pins, expected and actual
  result, pass/fail counts, evidence path, reviewer, limitations, cleanup and next action.
- Retry only classified transient I/O under a single retry owner. Preserve original failures;
  a rerun does not erase flakiness. Never lower a gate after seeing a failure to obtain green.
- Every phase has a recorded GPT 6 Luna Medium adversarial task/contract review before work.
  After validation, smoke and required gates, one GPT 6 Luna Medium work auditor checks the
  result/evidence/consumers. Findings must be resolved or keep the affected phase open.
  Both reviewers read the entire blueprint and apply the master plan's
  [blueprint review contract](MASTER_DEV_PLAN.md#blueprint-review-contract-for-both-reviewers),
  including preflight, four tools, complete attempt budgets and draft/critic/finalization/gate
  ordering. Receipts name blueprint headings/invariants and task/consumer/proof coverage;
  later obligations remain explicit. Missing coverage means the review is incomplete.
  For current P00-T05 the coordinator and that single post-auditor additionally inspect
  every development document against the complete blueprint; structural checks alone
  cannot pass that semantic audit. E-DOC-003 records both independent review receipts.

## P02 phase-local evidence boundary

P02 adds actual Qdrant named dense/BM25 native RRF k=60, authorized search/citation API,
scoped source revocation, exact ID/hash publication manifests and retrieval-only pilots.
Owner approved additive v3 with fresh/populated/rollback preservation tests. Runtime tools,
policy decisions, prompt exposure, graph and generated answers remain future obligations.
No P02 metric is a full B0/B1/B2 answer-system result.

## P01 phase-local evidence boundary

P01 checks strict contracts and every exact T01–T24 catalog ID, positive/negative fixture
labels and original spans; independent annotations remain PILOT. G-SOURCE P01 subset:
fresh schema, populated upgrades, rollback and unknown-schema preservation; persisted
approval/membership readers and immutable byte/range reads. G-SECURITY P01 subset:
backend identity/grants/case/tenant/source ACL, self-approval and revocation denials.
Index publication/reconciliation, citation API, live tools, model prompt exposure, graph
and full gate behavior belong to later phases. G-SOURCE/G-SECURITY stay PARTIAL.

## Gate catalog

| Gate | Owner phases / blueprint source | Falsifiable proof and required negative cases |
|---|---|---|
| G-DOC | P00 and every doc-affecting task; user suite request | `python palladion/docs/development/check_docs.py` and `--self-test`; local links/anchors, numeric/child IDs, required docs, section/invariant/case mappings, atomic fields/parents/acyclic dependencies and blueprint file ownership resolve. All ADRs have status/authority/question/why/options/recommendation/impact/editable answer/verification; accepted answers cannot be empty. Missing authority/question/impact/answer, metadata/ID, duplicate, unknown gate and cycle mutants rejected. Required pre-adversary/single post-auditor and coordinator whole-suite vision audit complete; checker cannot prove semantic fidelity or task size. |
| G-CONTRACT | P01; Core typed contracts, Test corpus | Planned `tests/test_goldens.py` plus typed schema tests: every case has scope, refs, required slots, policy basis/outcome, permitted hypotheses, forbidden claims and disposition. Invalid enums/unknown fields/naive times rejected; persisted envelopes schema-versioned; valid round trips pass. |
| G-SOURCE | P01/P02/P07; Ingestion and revocation | Planned `tests/test_ingest.py`: exact immutable bytes/spans/hash, authenticated approval separate from READY, failed/partial generations unpublishable, manifest exact IDs/counts, idempotency/recovery, revocation after cache/search and before release. Real citation API consumes original bytes; no source self-approval. Optional graph configuration changes required-index set explicitly. |
| G-RETRIEVAL | P02; Hybrid document retrieval | Planned `tests/test_retrieval.py`: actual Qdrant same-point dense/bm25, pinned compatible API/native RRF k=60 exactly once, exact-ID union, correct canonical filtering and post-expansion checks. Near IDs, opposite clauses, old/draft/restricted hits, missing exceptions, sparse outage and English/Indonesian fixtures. Measure stages/ANN-vs-exact; quality target calibrated later, not assumed. |
| G-TEMPORAL | P03; Policy-specific temporal applicability | Planned `tests/test_policy_temporal.py`: all four bases with trusted source; `[from,to)` exact boundaries, naive/untrusted/missing times, scoped supersession/revocation, historic knowledge cutoff, overlaps and mixed-basis migration. Larger revision/newer upload cannot break ties. Concurrent registry changes preserve conflict detection. |
| G-POLICY | P03; Policy evaluation contract | Planned `tests/test_policy_engine.py`: typed required facts with admissible evidence and freshness, bounded safe AST, all/any/not and comparison semantics, unsupported operator/type/depth rejection, conflicting rows and missing ≠ negative. Real gate consumer reads selected version/time/inputs/rows/source clauses in decision trace. |
| G-LIVE | P03; Live adapters, Failure taxonomy | Planned `tests/test_live.py`: allowlisted named operations only; backend case/target/tenant identity; unexpected schema/operation/URL/SQL/write rejected. All documented error classes, timeout/retry caps, redaction, response bounds, single-flight reads, distinct timestamp semantics; stale BI despite fresh read; consumers cannot authorize payment from OK alone. |
| G-BUDGET | P04/P06/P08; Exact call budget, Orchestration warning | Planned `tests/test_agent_budget.py`: 0–5 main incl final; failed/timeout/invalid JSON consume reserved attempts; concurrent calls cannot oversubscribe. ≤3 critic, ≤2 critic searches initial limit, all tools/prefetch/searches/retries included under explicit accounting, final slot reserved, no sixth repair. Deadline/cancellation stops work and safely persists state. |
| G-GATE | P04/P06; Claim-level assessment, Gate invariant | Planned `tests/test_gate.py`: five dispositions; every released verified material claim references admissible current-request evidence/rule trace. Unknown/wrong-scope/revoked/irrelevant refs, unmet policy slots, critical contradictions and unsupported actions blocked. PASS/score/answer-kind/hypothesis label cannot bypass checks. Final downgrade renders deterministic safe output. Semantic support checked against gold; not implied by ID existence. |
| G-MEMORY | P05; Continuity and Memory write protocol | Planned `tests/test_memory.py`: categories/scopes, append-only attempts incl failures, controlled promotion, user validity provenance/UNSPECIFIED, fresh-vs-historical observations, bounded regenerated packet, correction/close/revocation. Next API message reads actual persisted events then revalidates handles. Tampered grants and cross-user hot cache rejected. |
| G-CRITIC | P06; Structured reviewer contract | Planned `tests/test_critic.py`: normally one review, structured known claim/evidence refs, bounded scoped counter-search, revalidate new sources, invented challenge ≠ established conflict, supported exception revises claims. Required-review outage safely unavailable/partial; false-veto measurement and same-blind-spot fixture. |
| G-GRAPH | P07; Knowledge graph | Planned `tests/test_graph_identity.py`: real Neo4j constraints with concurrent duplicate verified identity; distinct IDs/similar names remain separate; provisional ID and reviewed merge trace. Allowed edge types, source-backed paths, hop/fan-out/node/time bounds, scope before exposure and after source resolution, graph-off/outage explicit. |
| G-SECURITY | Every runtime phase; Trust boundaries, Threat model | Planned `tests/test_security.py`: tenant/case/role/target scope at every boundary, source/graph/memory/tool prompt injection and poisoned approval, denied citation and mid-session revocation, tampered packet/arguments. Inspect prompts/responses/cache/diagnostics/audit for leaked content/existence; trace endpoint role-gated/redacted; zero unapproved operational side effects in written tests. |
| G-E2E | P04 onward, final P08; Full lifecycle, Walkthrough and ADR-0013 override | Planned `tests/test_end_to_end.py`: actual Groq-backed authenticated message endpoint to domain tools/ledger/gate, evidence GET and next-session packet. Supported informational, partial, conflict, not-established and unavailable cases; normative support still requires P06 critic. No evidence/tools, malformed results, outage/deadline yield useful safe outcomes. Deliberate deterministic failure tests are separate evidence and cannot replace actual-provider HTTP proof. Record model/quota/attempts; health/ready and cleanup smoke. |
| G-RESEARCH | P02/P06/P07/P08; Research evaluation | Planned `tests/test_goldens.py`, `scripts/evaluate.py`, `scripts/reconcile.py`: frozen run manifests, split integrity, metric denominator checks, reproducible retrieval, repeated stochastic runs, annotation adjudication, paired ablations, full failures/false vetoes, per-slice metrics and cost/tail latency. Scorer reads actual output artifacts, not model self-grades; missing measurements cannot become zero. |

## Atomic task coverage

Gate rows above own the assertions. Links below route to exact file-specific tasks in
the master plan; these are planned obligations, not passing evidence. Parent work
packages retain their original acceptance.

### G-BUDGET task coverage

[P04-T01.01](MASTER_DEV_PLAN.md#p04-t01-01), [P04-T01.03](MASTER_DEV_PLAN.md#p04-t01-03), [P04-T01.04](MASTER_DEV_PLAN.md#p04-t01-04), [P04-T02.01](MASTER_DEV_PLAN.md#p04-t02-01), [P04-T02.02](MASTER_DEV_PLAN.md#p04-t02-02), [P04-T02.03](MASTER_DEV_PLAN.md#p04-t02-03), [P06-T01.02](MASTER_DEV_PLAN.md#p06-t01-02), [P08-T02.04](MASTER_DEV_PLAN.md#p08-t02-04), [P08-T03.02](MASTER_DEV_PLAN.md#p08-t03-02).

### G-CONTRACT task coverage

[P01-T01.02](MASTER_DEV_PLAN.md#p01-t01-02), [P01-T01.03](MASTER_DEV_PLAN.md#p01-t01-03), [P01-T01.04](MASTER_DEV_PLAN.md#p01-t01-04), [P01-T02.01](MASTER_DEV_PLAN.md#p01-t02-01), [P01-T02.02](MASTER_DEV_PLAN.md#p01-t02-02), [P01-T04.01](MASTER_DEV_PLAN.md#p01-t04-01), [P01-T04.02](MASTER_DEV_PLAN.md#p01-t04-02), [P01-T04.03](MASTER_DEV_PLAN.md#p01-t04-03).

### G-CRITIC task coverage

[P06-T01.01](MASTER_DEV_PLAN.md#p06-t01-01), [P06-T01.02](MASTER_DEV_PLAN.md#p06-t01-02), [P06-T02.01](MASTER_DEV_PLAN.md#p06-t02-01), [P06-T02.02](MASTER_DEV_PLAN.md#p06-t02-02), [P08-T02.03](MASTER_DEV_PLAN.md#p08-t02-03).

### G-DOC task coverage

[P00-T04.01](MASTER_DEV_PLAN.md#p00-t04-01), [P00-T04.02](MASTER_DEV_PLAN.md#p00-t04-02), [P00-T04.03](MASTER_DEV_PLAN.md#p00-t04-03), [P00-T04.04](MASTER_DEV_PLAN.md#p00-t04-04), [P00-T04.05](MASTER_DEV_PLAN.md#p00-t04-05), [P00-T05.01](MASTER_DEV_PLAN.md#p00-t05-01), [P00-T05.02](MASTER_DEV_PLAN.md#p00-t05-02), [P00-T05.03](MASTER_DEV_PLAN.md#p00-t05-03), [P00-T05.04](MASTER_DEV_PLAN.md#p00-t05-04), [P01-T01.01](MASTER_DEV_PLAN.md#p01-t01-01).

### G-E2E task coverage

[P04-T04.01](MASTER_DEV_PLAN.md#p04-t04-01), [P04-T04.02](MASTER_DEV_PLAN.md#p04-t04-02), [P04-T04.03](MASTER_DEV_PLAN.md#p04-t04-03), [P05-T03.01](MASTER_DEV_PLAN.md#p05-t03-01), [P06-T02.02](MASTER_DEV_PLAN.md#p06-t02-02), [P08-T03.01](MASTER_DEV_PLAN.md#p08-t03-01), [P08-T03.02](MASTER_DEV_PLAN.md#p08-t03-02), [P08-T03.03](MASTER_DEV_PLAN.md#p08-t03-03).

### G-GATE task coverage

[P04-T02.02](MASTER_DEV_PLAN.md#p04-t02-02), [P04-T03.01](MASTER_DEV_PLAN.md#p04-t03-01), [P04-T03.02](MASTER_DEV_PLAN.md#p04-t03-02), [P04-T03.03](MASTER_DEV_PLAN.md#p04-t03-03), [P04-T03.04](MASTER_DEV_PLAN.md#p04-t03-04), [P04-T04.03](MASTER_DEV_PLAN.md#p04-t04-03), [P06-T02.01](MASTER_DEV_PLAN.md#p06-t02-01).

### G-GRAPH task coverage

[P07-T01.01](MASTER_DEV_PLAN.md#p07-t01-01), [P07-T01.02](MASTER_DEV_PLAN.md#p07-t01-02), [P07-T01.03](MASTER_DEV_PLAN.md#p07-t01-03), [P07-T02.01](MASTER_DEV_PLAN.md#p07-t02-01), [P07-T02.02](MASTER_DEV_PLAN.md#p07-t02-02).

### G-LIVE task coverage

[P03-T03.01](MASTER_DEV_PLAN.md#p03-t03-01), [P03-T03.02](MASTER_DEV_PLAN.md#p03-t03-02), [P03-T03.03](MASTER_DEV_PLAN.md#p03-t03-03), [P03-T03.04](MASTER_DEV_PLAN.md#p03-t03-04).

### G-MEMORY task coverage

[P04-T01.02](MASTER_DEV_PLAN.md#p04-t01-02), [P05-T01.01](MASTER_DEV_PLAN.md#p05-t01-01), [P05-T01.02](MASTER_DEV_PLAN.md#p05-t01-02), [P05-T02.01](MASTER_DEV_PLAN.md#p05-t02-01), [P05-T02.02](MASTER_DEV_PLAN.md#p05-t02-02), [P05-T02.03](MASTER_DEV_PLAN.md#p05-t02-03), [P05-T03.01](MASTER_DEV_PLAN.md#p05-t03-01), [P08-T02.06](MASTER_DEV_PLAN.md#p08-t02-06).

### G-POLICY task coverage

[P03-T01.01](MASTER_DEV_PLAN.md#p03-t01-01), [P03-T02.01](MASTER_DEV_PLAN.md#p03-t02-01), [P03-T02.02](MASTER_DEV_PLAN.md#p03-t02-02).

### G-RESEARCH task coverage

[P02-T04.04](MASTER_DEV_PLAN.md#p02-t04-04), [P05-T03.02](MASTER_DEV_PLAN.md#p05-t03-02), [P06-T03.01](MASTER_DEV_PLAN.md#p06-t03-01), [P06-T03.02](MASTER_DEV_PLAN.md#p06-t03-02), [P07-T03.01](MASTER_DEV_PLAN.md#p07-t03-01), [P08-T01.01](MASTER_DEV_PLAN.md#p08-t01-01), [P08-T01.02](MASTER_DEV_PLAN.md#p08-t01-02), [P08-T02.01](MASTER_DEV_PLAN.md#p08-t02-01), [P08-T02.02](MASTER_DEV_PLAN.md#p08-t02-02), [P08-T02.03](MASTER_DEV_PLAN.md#p08-t02-03), [P08-T02.04](MASTER_DEV_PLAN.md#p08-t02-04), [P08-T02.05](MASTER_DEV_PLAN.md#p08-t02-05), [P08-T02.06](MASTER_DEV_PLAN.md#p08-t02-06), [P08-T04.01](MASTER_DEV_PLAN.md#p08-t04-01).

### G-RETRIEVAL task coverage

[P02-T02.01](MASTER_DEV_PLAN.md#p02-t02-01), [P02-T02.02](MASTER_DEV_PLAN.md#p02-t02-02), [P02-T03.01](MASTER_DEV_PLAN.md#p02-t03-01), [P02-T03.03](MASTER_DEV_PLAN.md#p02-t03-03), [P02-T03.04](MASTER_DEV_PLAN.md#p02-t03-04), [P02-T03.05](MASTER_DEV_PLAN.md#p02-t03-05), [P02-T04.04](MASTER_DEV_PLAN.md#p02-t04-04), [P08-T02.05](MASTER_DEV_PLAN.md#p08-t02-05).

### G-SECURITY task coverage

[P01-T02.04](MASTER_DEV_PLAN.md#p01-t02-04), [P02-T01.03](MASTER_DEV_PLAN.md#p02-t01-03), [P02-T03.02](MASTER_DEV_PLAN.md#p02-t03-02), [P02-T04.01](MASTER_DEV_PLAN.md#p02-t04-01), [P02-T04.02](MASTER_DEV_PLAN.md#p02-t04-02), [P03-T03.03](MASTER_DEV_PLAN.md#p03-t03-03), [P04-T01.03](MASTER_DEV_PLAN.md#p04-t01-03), [P04-T04.02](MASTER_DEV_PLAN.md#p04-t04-02), [P05-T01.02](MASTER_DEV_PLAN.md#p05-t01-02), [P05-T02.03](MASTER_DEV_PLAN.md#p05-t02-03), [P07-T02.01](MASTER_DEV_PLAN.md#p07-t02-01), [P08-T03.01](MASTER_DEV_PLAN.md#p08-t03-01).

### G-SOURCE task coverage

[P01-T02.03](MASTER_DEV_PLAN.md#p01-t02-03), [P01-T03.01](MASTER_DEV_PLAN.md#p01-t03-01), [P01-T03.02](MASTER_DEV_PLAN.md#p01-t03-02), [P01-T03.03](MASTER_DEV_PLAN.md#p01-t03-03), [P02-T01.01](MASTER_DEV_PLAN.md#p02-t01-01), [P02-T01.02](MASTER_DEV_PLAN.md#p02-t01-02), [P02-T01.03](MASTER_DEV_PLAN.md#p02-t01-03), [P02-T01.04](MASTER_DEV_PLAN.md#p02-t01-04), [P02-T03.02](MASTER_DEV_PLAN.md#p02-t03-02), [P02-T04.01](MASTER_DEV_PLAN.md#p02-t04-01), [P02-T04.03](MASTER_DEV_PLAN.md#p02-t04-03), [P07-T02.02](MASTER_DEV_PLAN.md#p07-t02-02), [P08-T03.03](MASTER_DEV_PLAN.md#p08-t03-03).

### G-TEMPORAL task coverage

[P03-T01.02](MASTER_DEV_PLAN.md#p03-t01-02), [P03-T01.03](MASTER_DEV_PLAN.md#p03-t01-03), [P03-T01.04](MASTER_DEV_PLAN.md#p03-t01-04).

## Fixed integrity targets and empirical targets

Blueprint “Initial acceptance gates” requires, on the declared test set, 100% of released
verified material claims to reference existing currently authorized evidence IDs or approved
rule traces; zero successful restricted-content leaks; zero unapproved operational side
effects; correct resolution for every authored temporal fixture; and correct no-evidence,
no-tool and contradiction handling. Denominators and attempt counts must be reported.
Zero observed leaks is a test result, not a production guarantee. A refusal-only system
must still be scored for usefulness, abstention precision and answer coverage.

Retrieval recall/improvement, unsupported-claim reduction, acceptable p95 latency/cost,
critic retention and graph benefit thresholds are **unset**. After B0/B1 development runs,
preregister numerical targets and sample/repetition protocol before the final held-out run
(Q08). Do not mark G-RESEARCH passed merely because the script produced a file.

## Hard-case coverage from the blueprint

These IDs retain the blueprint's meaning. Tests remain planned. Some outcomes depend on
declared context; never rewrite `POLICY_CONFLICT` (policy result) as though it were the
same enum as final `CONFLICT` without a tested mapping.

| Case | Required observation | Owner task | Gate |
|---|---|---|---|
| T01 | Similar old SOP cannot win against applicable approved policy | P02-T03 | G-RETRIEVAL, G-GATE |
| T02 | Historical transaction and current handling resolve distinct time bases | P03-T01 | G-TEMPORAL |
| T03 | Overlapping approved policies without precedence return POLICY_CONFLICT | P03-T01 | G-TEMPORAL |
| T04 | Missing/untrusted transaction timestamp produces typed time failure | P03-T01 | G-TEMPORAL |
| T05 | Same labels, distinct verified entity IDs never merge | P07-T01 | G-GRAPH |
| T06 | Concurrent ingestion of verified identity satisfies uniqueness | P07-T01 | G-GRAPH |
| T07 | Restricted graph neighbor never reaches model or citation reader | P07-T02 | G-GRAPH, G-SECURITY |
| T08 | Cached source revoked before release cannot authorize claim | P02-T04 | G-SOURCE, G-GATE |
| T09 | Reported debit, absent settlement: partial and no reversal | P04-T04 | G-E2E, G-GATE |
| T10 | Supported critic exception is revalidated and corrects draft | P06-T01 | G-CRITIC |
| T11 | Invented critic source/challenge rejected without fabricated conflict | P06-T01 | G-CRITIC |
| T12 | Withheld appendix: no external inventory-completeness claim | P08-T02 | G-RESEARCH, G-GATE |
| T13 | Old data_as_of stays stale despite fresh observed_at | P03-T03 | G-LIVE |
| T14 | Tenant B sees no tenant A memory/graph content or existence leak | P08-T03 | G-SECURITY |
| T15 | Refund injection in uploaded source remains untrusted data | P08-T03 | G-SECURITY |
| T16 | Four investigation calls reserve fifth final, never sixth | P04-T02 | G-BUDGET |
| T17 | Fourth critic call / third counter-search refused and logged | P06-T01 | G-BUDGET |
| T18 | Sparse outage reported as degraded verification, not exhaustive absence | P02-T03 | G-RETRIEVAL |
| T19 | POL-17 not substituted with POL-71 | P02-T03 | G-RETRIEVAL |
| T20 | No user expiry stays UNSPECIFIED; no model TTL | P05-T01 | G-MEMORY |
| T21 | Revoked old source only authorized historical audit, no current directive | P03-T01 | G-TEMPORAL, G-SOURCE |
| T22 | Scoped BI NOT_FOUND plus transaction outage ≠ universal absence | P03-T03 | G-LIVE, G-GATE |
| T23 | High-degree graph traversal obeys resource caps | P07-T02 | G-GRAPH |
| T24 | Normative critic outage yields explicit safe partial/unavailable | P06-T02 | G-CRITIC, G-GATE |

Additional required checks: partial ingestion/recovery; source hash/span mismatch; half-open
interval edges and mixed time bases; unsupported operator/AST depth; stale cache after
role change; packet principal tampering; no evidence/no tool access; irrelevant but valid
citation; tool/model failures counting budget; error/cancellation cleanup; privileged trace
and log redaction. These extend the 24 cases without renumbering them.

## Validation commands and smoke procedures

Now, from repository root:

These documentation-only commands use the existing Python interpreter, without creating
the application environment. Separate machine repair installed uv and the user created
the ignored app .venv (E-DOC-004); P02 dependency/real-index setup is authorized; generative model integration remains P04.

```powershell
python palladion/docs/development/check_docs.py
python palladion/docs/development/check_docs.py --self-test
git diff --check
```

Later Python tasks, from `palladion/`: after GO verify/reuse the app-local `.venv`;
use `uv venv` only if absent and after ignore protection is verified. Pin dependencies
with `uv.lock` and document actual interpreter/tool commands. Package
choices are delegated within blueprint scope. Expected tooling is pytest plus configured
lint/type/build checks. A planned targeted example is
`uv run --locked pytest tests/test_policy_temporal.py tests/test_policy_engine.py`.
Run the actual manifest checks. P01 commands from palladion/: uv sync --locked;
uv run --locked --no-env-file pytest; ruff check .; mypy; python -m build;
python scripts/validate_foundation.py. Use the uv run prefix for each tool as in README.

For runnable API slices: start an isolated application using its documented entry point;
check health/readiness without leaking internals; authenticate synthetic principal; upload
and approve a fixture under separate roles; submit case message; read every returned
citation back; change/revoke fixture scope and repeat the forbidden path; make a follow-up
request and inspect its persisted state. Record five dispositions in the full P04/P08 suite.
Actual Groq runs prove generative integration and supply model-quality observations;
pure deterministic guard tests prove only their checked mechanics. Free-plan rate/access
failure is a recorded blocker/degradation, never substituted successful model evidence.
Load the repository-root `.env` only for explicit enabled commands, never print/copy it.

Record process IDs/ports and fixture directories before starting. Stop only task-owned
processes and verify their recorded ports have no listeners. Do not use destructive
Compose volume teardown or kill unrelated services as a cleanup shortcut.
