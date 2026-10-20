# P09 audit and benchmark handoff

Owner authorization: 2026-10-20 end-to-end reaudit and Palladion-side work from
benchmark PALLADION_FIXES Part B. P00–P08 remain historical completed pilot work;
these new findings reopen the affected guarantees, not the immutable experiment.
Owner subsequently authorized completion notes in the benchmark handoff document and a
scoped verified main push. Benchmark implementation/editor edits, UI and enterprise
writes remain excluded.

## Independent review receipts

The owner explicitly allowed additional auditors for this run only. Five read-only
GPT 6 Luna Medium auditors read the complete blueprint directly. They had no permission
to run tests, contact providers/services, inspect credentials, edit files or mutate git.
The standing start/end-only delegation rule remains unchanged for subsequent work.

| Reviewer | Scope | Findings and disposition |
|---|---|---|
| system_reaudit_runtime | Blueprint §1–18, runtime/preflight/tools/critic/final gate | Confirmed: RULE_REQUIREMENT can be SUPPORTED without current critic review when policy inputs are complete. Owning correction and positive/negative regression required. |
| benchmark_handoff_adversary | Blueprint §1–18, Part B PF01–PF06 and actual consumers | PF01–03 real gaps; PF04/05 need explicit new contracts; PF06 assumes obsolete missing critic. Retracted initial assertion that B5 disables final gate: B4/B5 disable critic only and still call gate. Preserve invariants and disclose unsupported controls. |
| code_audit_storage_security | Blueprint §1–18, source approval, ACL, provenance, graph/storage | No confirmed vulnerability. Synthetic demo_auth.json bounds/owner permissions are a shared-host hardening suggestion, deferred to separately authorized deployment work. |
| code_audit_memory_evaluation | Blueprint §1–18, memory ownership/readback, evaluation/accounting | Confirmed: run_max_seconds checked only before model calls, not whole lifecycle. Consumed adapters.yaml bytes absent from source snapshot. Bound whole run and snapshot consumed configuration; legacy artifacts remain unchanged and limited. |
| code_audit_test_proof | Blueprint §1–18, T01–T24 mapping and evidence | T01 mapped checks do not prove full old-SOP query→policy→gate scenario. T12 inventory_attested=false is a constant telemetry field, not a behavioral semantic completeness score. Add consumer controls and withdraw the broader claim. |

All findings are coordinator-verified source observations, not yet verified fixes.
Reviewers recommend; coordinator owns decisions, checks and closure. Reuse these
reviewers for resolution; no further agents are needed.

## Baseline and proof obligations

Fresh credential-free source baseline: 362 PASS, 28 explicit SKIP, one warning,
63.59 seconds. Command: `.venv/Scripts/python.exe -m pytest -q --basetemp
runtime/pf-baseline-20261020 --junitxml runtime/pf-baseline.xml`, full output in
`runtime/pf-baseline.log`. No provider or real-server gate was enabled. This baseline
does not refute the audit defects: their defining conjunctions are absent from tests.

PF01: optional aware document as_of, current ACL/revocation preserved; do not turn it
into trusted operational event time. Citation readback must obey the same cutoff.
PF02: bounded approval-owned family/revision/identifier aliases; keep strict unknown
structured identifier behavior. Do not silently require admin rights from existing
uploader pipeline consumers.
PF03: reconcile physical index in bounded batches; no TTL or health bypass that hides
drift. Report full authorized counts and truncation honestly; benchmark before claiming
latency improvement.
PF04: optional HTTP limit up to40/default12 and whole-passage retrieval-tokenizer budget;
domain tool remains capped12. Explicit tokenizer identity/counting; not provider billing.
PF05: scoped admin provisioning only with owner-approved grants/auth contract; no bearer
minting, admin escalation or idempotent restoration of revoked access.
PF06: capability matrix for existing isolated evaluator controls; serving gate, source
authority, parser, deterministic preflight and time boundaries remain mandatory.

Required closure: regression controls, stack validation, actual HTTP/CLI consumer smoke,
applicable real-service checks, reused independent end review and resolved findings,
fresh docs/learning/evidence, owned-port cleanup and deliberate verified commit.


## PF03 continued performance investigation (ADR0091 rejected closure)

Retained isolated384-dimensional deterministic transport corpus: runtime/p09-perf-current.json
points to its canonical database and UUID Qdrant collection. This is not a semantic/model
latency study. Other local work remained running; timing samples are not capacity claims.

- Profile identity versus explicit gzip:5438862 versus1698216wirebytes, decoded bytes
  unchanged (approximately69% smaller). Profiled elapsed1.1315 versus0.8506seconds.
  Follow-up response instrumentation confirms the default client already negotiates
  `gzip, deflate` and every observed response uses gzip. No new compression default shipped.
- Three-repeat REST-default/gRPC1000-source medians0.6165/0.5763seconds. No transport
  change shipped; cold-start and small-sample differences do not prove superiority.
- Canonical batching reduces SQL statements1000sources7006→29 and10sources76→14.
  Five timed repetitions after one warmup: previous1000median0.5582seconds;
  bulk1000median0.5792seconds. These observations do not establish an end-to-end speedup.
  Five mid-read source/ACL/generation/membership/grant negative controls and130-source
  SQL-count/physical-drift control pass in15focused tests.
- Runtime-only batch-size experiment (not shipped)64/256/1000:1000-source medians
  0.4634/0.3315/0.5656seconds. Even256 remains approximately31times its10-source
  median0.01055seconds. The experiment overlaps credential-free regression execution;
  no isolated host or broad scaling conclusion is claimed.

Raw commands/scripts/logs and JSON: runtime/p09-profile.log,
root/{results,transport-comparison,bulk-comparison,batch-size-comparison}.json,
runtime/p09-{bulk,batch}-measure.log and runtime/p09_bulk_measure.py /
p09_batch_measure.py. No provider calls, no physical checks omitted, no TTL cache.
Original PF03 performance target stays OPEN. ADR0095 asks separately about explicit
bounded audit reuse; no answer or freshness weakening is inferred.


## Approved five-second cache: observed benefit and retained overhead

ADR0095 owner answer authorizes implementation but directs leaving PF03 open if worse.
Reused memory/evaluation pre-adversary challenged complete-aggregate scope/backend
identity and explicit consumer flags; main verified public SDK endpoint identity with
credential-bearing URLs rejected and custom/local clients bypassed. Sole end reviewer
found no remaining confirmed cache/source-authority defect, and withdrew a suggested
completion timestamp: audit-start expiry conservatively bounds the earliest read point.

Initial five-repeat run: HTTP fresh10/1000 medians0.1963/0.7971seconds; enabled warm-hit
10/1000medians0.1110/0.2525seconds. Coverage-only1000fresh0.8053 versushit0.08239seconds,
but10sourcecoveragehit0.02375 versusfresh0.01324seconds. Full JSON in root/cache-comparison.json.
These ordered samples alone are insufficient to establish general improvement.

Balanced rotating-order follow-up retains all20primary observations, including expiry:

| Sources | Strict median (s) | Enabled median (s) | Enabled HIT / MISS |
|---|---|---|---|
|10|0.26603|0.31547|4/1|
|1000|2.15143|0.88834|3/2|

Three deliberately cold enabled misses per size have medians10=0.22613seconds and
1000=2.08826seconds. Healthy exact counts,10passages and statusOK asserted for every
HTTP observation. Additional warmup requests and their costs/statuses are retained;
not hidden retries. First driver incorrectly asserted every post-warm request must HIT:
one expired between warmup and timed request. Its failed log is preserved, and corrected
driver records normal misses instead of forcing refresh or discarding them.

Raw runtime/p09-cache-paired.log (failed driver), p09-cache-paired-r2.log and
p09_cache_paired_r2.py; complete root/cache-paired-http-r2.json. Synthetic constant384D
transport encoder, real Qdrant BM25/dense/HTTP/canonical readers; no semantic/retrieval
quality claim. Other local work and credential-free regression execution overlapped;
no isolated-host, tail/capacity or causal provider result is claimed. Compression remained
gzip default and physical batch/page bounds stayed64/256. No TTL renewal on hit.

Disposition: cache is explicitly opt-in, current canonical authorization remains fresh,
and PF03/P09-T02.07 remain OPEN because measured small-case overhead and expiry/cold
costs do not establish the original acceptance across workloads. This is not a waived
target or an implicit serving-default change. PF01/02/04/05/06 verified consumer contracts
are documented in the scoped benchmark handoff response; unsupported PF06 bypasses stay
unsupported under owner-approved scope.
