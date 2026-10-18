# Benchmark testing gates

Only BG-DOC is runnable today. Every other gate is `NOT_RUN` and describes the full obligation
of its owning phases; phase-local results never imply a full-gate pass. Gate states and evidence
are in [PROGRESS](PROGRESS.md) and [EVIDENCE_LOG](EVIDENCE_LOG.md). Gates test the benchmark's
own correctness. They do not test, and cannot establish, how well Palladion or any comparator performs.

## Execution and evidence rules

- Derive tests from the protocol and the task card. Every guard needs a violating case that
  fails and a valid case that passes. A metric needs controls: a perfect, an empty and a shuffled
  system must score differently, and a hand-computed case must match.
- A gate passes only after its acceptance is observed through the producer and its real consumer
  (for example, the scorer reading a run directory written by the runner). A helper with no caller,
  a matching string or a passing import is not integration.
- Deterministic tests may inject data or errors into the benchmark's own guards. They do not establish
  provider or Palladion behavior; those claims need a real call, recorded with model, configuration and quota.
- Multi-phase gates stay PARTIAL with the covered and uncovered obligations listed until the whole contract passes.
- Record revision, task and gate, exact command and working directory, pins, expected and actual result,
  counts, evidence path, limits, cleanup and next action. Never filter output to success lines or
  truncate before a possible failure. A bounded search proves only its scope.
- A failed or missing run is a result (`NOT_RUN`, `UNSUPPORTED`, `FEATURE_NOT_SUPPORTED`, `INVALID_RUN`,
  `TIMEOUT`), never a zero score and never silently dropped. A rerun does not erase the first outcome.
- Never lower a gate or change a metric after seeing a failure to obtain green. Changes made before
  measurement carry a rationale in ADR_LOG; changes after the test seal flag later results exploratory.
- No ambient credentials. Provider calls need an explicit enable flag, a recorded budget and the model
  name in the command; credential presence is not intent. Free-tier quota limits are enforced, not hoped for.
- Inspect any destructive path (index rebuild, namespace clean-up, teardown) before running it; back up
  persistent stores first. Stop only processes the task started and verify their ports are free.
- Numeric tolerances ("within tolerance", "near nominal", agreement and decoy-audit thresholds) are fixed in an ADR
  before the first measurement that uses them; a proof without a recorded number is not yet runnable.
- Before each phase one Haiku 5.5 reviewer tries to refute its tasks and proof; after its gates pass, one
  Haiku 5.5 auditor checks the work. Both read the complete protocol. Findings are resolved or keep the phase open.

## Gate catalog

| Gate | Owner phases / protocol source | Falsifiable proof and required negative cases |
|---|---|---|
| BG-DOC | B00 and every doc-affecting task; whole suite | `python palladion-benchmark/docs/development/check_docs.py` and `--self-test`: required documents, local links and anchors, stable IDs, ADR fields, atomic fields, acyclic dependencies, ownership of all 70 protocol-tree files, coverage rows. Planted broken link, missing field, cycle and unowned file are rejected. The checker cannot prove semantic fidelity; the independent review does that. |
| BG-HARNESS | B01; §3.1, §7, §18 | `tests/test_adapter_contracts.py`, `tests/test_budget_enforcement.py`, `tests/test_generator_pool.py`: contracts reject invalid input, null stays null, a sixth main call is a recorded failure, failover is explicit and per-call recorded, a crashing arm becomes `INVALID_RUN`. Real-provider proof of the generator entry point is separate and recorded (B01-T05.02). |
| BG-FIXTURE | B02, B07-T07, B08-T01; §4, §16 | `tests/test_fixture_integrity.py`, `tests/test_temporal_gold.py`: determinism, referential integrity, contradiction really covers the same scope and time, distinct namespaces never merge, supersession acyclic, draft claiming approval stays unapproved, no leakage of gold into the published corpus. Every check has a planted-defect control. |
| BG-GOLD | B02, B05, B07, B08; §5, §6, §14.5 | `tests/test_evidence_slots.py` plus the label audit: alternatives, empty-alternatives meaning, five negative mechanisms distinct from conflict, family-grouped splits, two-annotator agreement with denominators, defective cases fixed or withdrawn before sealing. |
| BG-METRIC | B03, B05, B06, B07; §8–§11 | `tests/test_span_alignment.py`, `tests/test_evidence_slots.py` and metric unit tests: hand-computed values, oracle/empty/shuffled controls, wrong-vintage counted though ranked first, fabricated locator caught, always-abstain penalized, no metric reads a self-reported score as a probability. |
| BG-STATS | B03-T04, B08-T02; §13.2, §14.2, §14.3 | `tests/test_statistics.py`: simulated known effect recovered, interval coverage near nominal, clustered interval wider than naive, exact McNemar and Holm against known tables, zero-failure bound, calibration measures against hand cases. |
| BG-ADAPTER | B01-T03, B04, B06, B07; §2, §7.1 | `tests/test_adapter_contracts.py`: each arm registers its capabilities, unsupported capability is explicit, no phantom native citation, no import of the system under test, unavailable service gives `NOT_RUN`, official comparator path preserved with pin and deviations recorded. |
| BG-FAIR | B04, B05, B06, B07; §3.1 | Run-validator checks: same snapshot and principal, equal counted evidence tokens, same generator family and prompt in Tracks A/B, matched call budgets, indexing and extraction cost included, C1 and C2 differ only in declared metadata, mixed-model pairs flagged. |
| BG-TRACKA | B04, B06, B08, B09; §3 Track A | `scripts/run_track_a.py` writes artifacts the scorer reads; artifacts hold no gold field; arms not run listed with a reason; pilot results labeled pilot and excluded from held-out claims. |
| BG-TRACKB | B05, B08, B09; §3 Track B | `scripts/run_track_b.py`: shared generator and runtime gate, per-call model recorded, no hidden gold, stochastic subset repeated at least three times in the confirmatory run, real-provider responses. |
| BG-TRACKC | B07, B08; §3 Track C | `scripts/run_track_c.py`: per-arm budgets, per-case reset, no state reset inside an episode, no leakage across independent episodes, actual invocation counts reported by each system. |
| BG-SECURITY | B02, B03, B04, B07; §16.3, §8.3 | Tenant and role isolation in the fixtures, forbidden-source exposure counted, injection documents inert in the harness, no real secrets or customer data, secret scan with a working negative control, evaluator-only gold never in arm-visible paths. Zero observed leaks is reported with its upper bound, not as zero risk. |
| BG-PREREG | B08; §22 | Protocol checklist complete, methods and code frozen, test manifests sealed with SHA-256, primary pairings and equivalence margin fixed, tuning log shows no locked-test reads, edit-after-seal detected. |
| BG-ABLATION | B08-T05; §15 | Each of A01–A16 removes exactly one component or substitutes a defined comparator against a stated base; system-capability ablations (A09, A14) and the fixture-only gate-off run (A15) are labeled as such; declared factorials reported. |
| BG-REPRO | B01-T03, B02-T07, B04, B08-T07; §7.2, §14.4, §19.3 | Manifests immutable and complete, `latest` rejected, same seed gives the same digest, result validator rejects planted leakage and hash mismatch, a reader can reconstruct a run from its manifest. |
| BG-REPORT | B03-T06, B08-T06; §13 | Tables list run states beside scores, report has negative-findings and fairness-deviation sections, no composite is the sole winner, dominated arms are marked from data, severe-failure counts shown. |

## Mutation coverage (protocol §16.1)

Each mutation changes a fixture in the declared way. Its gold expectation and failure metric are those in the
row of the same name in protocol §16.1, which B07-T07.01 copies into the fixture records; this table does not
restate them. All are generated by B07-T07.01 and exercised through the Track runners afterward.

| ID | Mutation | Owner task | Gates |
|---|---|---|---|
| M01 | Wrong latest version: newer but not yet effective SOP | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M02 | Retroactive rule with explicit event-time scope | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M03 | Invalid supersession chain (duplicate, cycle, conflict) | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M04 | Authority spoof: draft claims board approval in its body | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| M05 | Negation twin: same sentence except "must not" | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M06 | Tenant collision: same merchant name in two namespaces | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| M07 | Poisoned graph: inferred REQUIRES edge without a supporting citation | B07-T07.01 | BG-FIXTURE, BG-METRIC |
| M08 | Unindexed approved SOP: registry row present, chunk missing from an index | B07-T07.01 | BG-FIXTURE, BG-REPRO |
| M09 | ACL revoke: a visible passage revoked between turns | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| M10 | Policy update between two chat turns | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M11 | Live outage: transaction API returns 503 | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M12 | Live stale result older than the operation's bound | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M13 | Memory poisoning: user chat claims a cap was removed | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| M14 | Prompt injection inside a source PDF | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| M15 | Graph hub overload through a generic entity | B07-T07.01 | BG-FIXTURE, BG-METRIC |
| M16 | Counterevidence omission: critical exception absent from first top-K | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M17 | Bilingual alias: Indonesian slang for an English technical term | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M18 | Partial support: cause explained, authorization missing | B07-T07.01 | BG-FIXTURE, BG-GOLD |
| M19 | Contradiction: two equally approved rules overlap in scope and time | B07-T07.01 | BG-FIXTURE, BG-GOLD |

## Metamorphic invariants (protocol §16.2)

| ID | Invariant | Owner task | Gates |
|---|---|---|---|
| MT01 | Paraphrase invariance: same facts reworded give the same policy outcome and gold citations | B07-T07.01 | BG-GOLD, BG-METRIC |
| MT02 | Authorized-role invariance: widening access adds visible evidence but does not validate earlier unauthorized answers | B07-T07.01 | BG-GOLD, BG-SECURITY |
| MT03 | Version monotonicity: adding a future-effective version does not change a past event-time outcome | B07-T07.01 | BG-GOLD, BG-FIXTURE |
| MT04 | Evidence addition turns a justified abstention into an answer | B07-T07.01 | BG-GOLD, BG-METRIC |
| MT05 | Counterevidence addition revises the answer or identifies a conflict | B07-T07.01 | BG-GOLD, BG-METRIC |
| MT06 | Unrelated-document insertion leaves gold facts unchanged and degradation is monitored | B07-T07.01 | BG-FIXTURE, BG-METRIC |
| MT07 | Title permutation leaves identity, merges and authority unchanged | B07-T07.01 | BG-FIXTURE, BG-SECURITY |

## Atomic task coverage

Every card in the [master plan register](MASTER_DEV_PLAN.md#atomic-execution-register) names its
gate and the observation that could fail. Phase exits require their own tasks and gates, not later
capabilities. A phase never claims a multi-phase gate passed ahead of its consumers.
