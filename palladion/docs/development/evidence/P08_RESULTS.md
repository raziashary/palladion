# P08 synthetic pilot results

Status: P08 engineering pilot complete; sole independent end review and same-reviewer
resolution verified at E-P08-003. No hypothesis/semantic efficacy claim. Dates span2026-10-19UTC/2026-10-20Asia-Bangkok.

## What the measurements establish

The owner-approved grid recorded all44planned observations across11arms,2synthetic
case families and2repetitions. It recorded16row-level errors. Of91model attempts,
41received provider responses,45returnedHTTP429,2returnedHTTP400 and3were cancelled.
Known received usage totals54750tokens; failed-request usage and actual billing are
unknown. The28harness responses include15VERIFICATION_UNAVAILABLE dispositions and
must not be described as28successful model answers. Other received dispositions were
11PARTIALLY_SUPPORTED,1SUPPORTED and1NOT_ESTABLISHED.

All12released citations resolved through the canonical reader. The restricted markers
were absent from all91recorded attempt-input message sets and44responses; the actual
uploaded-injection/API check separately verified absence from cache, memory and trace.
This is evidence for these supplied controls, not a universal confidentiality guarantee.

Most arms missed the frozen50%exact-quote target. No model, planner, adaptive-review,
fusion, graph or vector-memory superiority follows from this quota-affected tiny pilot.
Semantic support, usefulness and causal false-veto accuracy remain UNKNOWN without
independent human adjudication. Serving defaults remain unchanged.

## All-attempt outcomes

Every arm has4planned observations. Quote recovery uses all4, including errors.
Harness responses may be qualified/unavailable; they are separate from provider success.

| Arm | Harness responses / errors | Exact quote recovery | Calls | p95 request seconds |
|---|---:|---:|---:|---:|
| B0 lexical |2/2|1/4|4|10.155|
| B1 native hybrid |0/4|0/4|4|13.755|
| B2 reranked/context |1/3|1/4|4|10.331|
| B3 optional graph |2/2|2/4|4|29.217|
| B4 policy, no continuity/review |4/0|2/4|10|39.839|
| B5 continuity, no review |3/1|0/4|9|54.015|
| B5_VECTOR augmentation |4/0|1/4|9|35.148|
| B6 mandatory critic |4/0|1/4|13|54.143|
| B7 adaptive critic |4/0|0/4|11|43.891|
| B8 nonexclusive planner |2/2|1/4|19|60.022|
| B9 alternative fusion |2/2|2/4|4|11.319|

The16row errors comprise13HTTP429 and3timeouts. Additional failed model attempts
were caught by the harness and yielded explicit unavailable/qualified responses.
The60.022second p95 includes deadline cancellation/cleanup overhead; it is not a
claim of a hard60.000second wall-clock guarantee. Latencies include10second call
spacing. Resource/provider contention and changing quota availability prevent a causal
capacity comparison. A separate frozen-draft critic run overlapped the later grid;
that concurrency is a limitation, not an unreported controlled condition.

## Paired comparisons and interpretation limits

The receipt includes case-cluster bootstrap results over all-attempt elapsed time,
seed1719/1000resamples. Repetitions are averaged within eachcase, leaving only2clusters.
For B7−B6 the measured mean difference is−10.446seconds, interval[−25.618,4.726].
This interval and the failed attempts do not establish an adaptive-review benefit.
No semantic interval or hypothesis-success value is manufactured.

B7 comparesB6; B8 comparesB6; vector augmentation comparesB5. B9 records identical
raw dense/sparse candidate lists for k60RRF and min-maxCombSUM, then passes the
alternative through the canonical consumer with native fusion bypassed. Its B2
generated-answer parent is a separate native-retrieval observation; raw rank controls
and stochastic generated answers must not be conflated into a causal fusion claim.
Only one selected fusion method produces each answer's candidate order.

The two-session mechanism supplies a prior preference, not a full long-running
investigation or human personalization study. Fixture label `historical` is metadata;
this grid does not execute historical as_of queries. Separate temporal/continuity/
critic and T01–T24 regression evidence carries those engineering obligations.
Unobserved unanswerable slices remain NOT_APPLICABLE.

## Reproduction and retained evidence

- [Approved protocol](P08_PROTOCOL_FREEZE.md) and [immutable machine freeze](p08-approved-protocol.json).
- [Bounded public receipt](p08-pilot-receipt.json):less than256KiB,44scoreable
  observations,91attempt summaries, hashes, failure codes, canary counts and paired costs.
  Raw prompts, source snapshots, originals and canonical stores are retained locally
  under `palladion/runtime/evaluation/p08_0d19c2375c5c46d3ac792fd3c1e5da20/`.
- Full raw replay, from the application directory:

```powershell
uv run --locked --no-env-file python scripts/evaluate.py --replay-study runtime/evaluation/p08_0d19c2375c5c46d3ac792fd3c1e5da20
```

The reader validates manifest/completion/input/source/call/row hashes and accounting
before scoring. It makes no provider request. Public mechanical metrics can also be
recomputed with `core.evaluation.score_study_rows(receipt['observations'])`; the export
checked exact canonical-digest equality against the complete raw replay's metrics.
The public receipt is a bounded measurement record, not the raw source authority store.

## Fresh frozen-draft critic control

Separate current-artifact20B run p06-57815987982f4322997fc434305ebe83 completed
all16conditions across exception/correct-fact/missing-input/withheld-appendix cases.
Known fact retention16/16; full exception-quote corrections0/4; inventory attestations0.
Retention includes deterministic qualified fallbacks after provider failures; it does
not mean16successful generative reviews or answers.
Thirty model invocations were started across the controlled conditions; canonical
attempt events retain3RECEIVED,3SCHEMA_INVALID and25FAILED events. Terminal validation
annotations can accompany the same invocation, so these event counts are not summed
as distinct calls. Known received usage8077tokens excludes the separate runtime check
and unknown failed usage. That runtime HTTP200 resolved its citations but did not release
the full exception quote and recorded a provider429. No correction efficacy follows.

Groq reported20B daily quota199674/200000tokens during this run. No call was retried.
Earlier aborted runs remain retained. The separate continuity control explicitly uses
owner-approved120B under ADR0084; it is not pooled with this run or the frozen grid.

## Fresh continuity control

Separate120B run p05-b55c4c1197d646f299746de55263886f completed all3conditions with
mandatory review held constant. Its exact script snapshot SHA256 is
1c90793594c1c0778d1c22be06894d54130ea44ca63b9c6f84c2ef37ed4043c3.
All3released the current mock observation, no stale-state claim, and resolvable
citations. StandardB5 retained the required settlement_state gap in its packet but
omitted it from the answer. B5-compressed retained it in both. All3mechanical completion
flags are false because completion requires the full disposition/verification criteria.

| Continuity condition | Packet chars | Packet gap recall | Answer gap recall | Seconds |
|---|---:|---:|---:|---:|
| B4 memory off |611|0/1|1/1|41.933|
| B5 standard |4231|1/1|0/1|41.852|
| B5 compressed |1310|1/1|1/1|60.130|

Initial plus follow-up requests started22model calls (15main/7critic), with32859known
received tokens; attempt events include4FAILED,3SCHEMA_INVALID and1CANCELLED. All3
conditions preserve provider tool_use_failed400 diagnostics. This tiny control proves
some context/current-reader wiring and exposes omission; it does not establish a
memory benefit. [Supplemental bounded receipt](p08-controls-receipt.json) binds both
fresh controls, per-condition mechanics/attempts and original artifact hashes. Raw
reports and the exact continuity script snapshot remain under ignored runtime storage.

## Retrieval measurement correction (end-review R4)

The frozen source passed the final top-four evidence packet into a helper whose default
labels were Recall@5/10/20. Those raw legacy labels are withdrawn: they cannot observe
candidate ranks5–20. Candidate/fused/reranked-stage @5/10/20 and full-ranking MRR are
UNAVAILABLE in this pilot. No candidate-stage improvement is claimed. The final packet
and all original inputs/source/rows/calls/completion hashes remain unchanged. Exact-quote
recovery, citation readback and call/cost tables above do not use those invalid labels.

ADR0086 corrects future scoring to explicitly observed final-packet @4/packet-MRR and
marks unobserved candidate ranks unknown. Current replay/public receipt carries the
withdrawal notice, not invented replacement stage values. A new frozen full-stage run
would be needed for fresh candidate-quality claims. Rank5/rank10 and actual canonical
consumer guards verify the cutoff distinction and unchanged four-item model packet.

## Engineering verification and remaining closeout

Final source suite360PASS/28explicitSKIP518.39seconds. Actual source-injection
check1PASS98.70seconds. Before the reporting-only R4 correction, wheel focused controls37PASS39.21seconds.
Final wheel after R4 passes20installed report/cutoff checks4.00seconds and all65packaged
source files match. Final wheel SHA256:
d9795234c8820cc97de5df6200616fffed97cbfd4726fc4537774bd3167a0a3d.
Final installed CLI replay reconstructs all44rows with the retrieval measurement notice.
The previous HTTP/7integration checks exercise unchanged serving modules; R4 changes
only core measurement helpers and the isolated evaluator/replay. Installed HTTP health, search, canonical
citation readback, cross-tenant denial and disabled-model response pass with0providercalls.
Two local-model rerunsPASS30.30seconds; original failed server sweeps are preserved.

With the owner's other workloads left running, Neo4j was restarted and our remaining
checks serialized. All7missing installed integration checks nowPASS217.35seconds,
including identity uniqueness, bounded traversal, restricted graph/API/tool access,
cache revocation, critic correction control, sparse outage and exact-source reconciliation.
No graph query rewrite, deadline expansion or foreign process termination was used.
Current T01–T24 reconciliation is24PASS; the separate historical reconciliation remains
20PASS/4FAIL. Both inputs/hashes/results are retained in the supplemental receipt.
These are concrete control results, not semantic certification or a capacity guarantee.

Final report/scorer guards18PASS3.34seconds; docs19Markdown/98cards/20negativecontrols,
Ruff/strictmypy and dependency checks pass. The single independent end audit read the complete blueprint and all development
records; all material findings are resolved, including the R4 measurement withdrawal.
The verified scoped checkpoint containing this report preserves the engineering pilot. Owned process/port cleanup is
verified: Qdrant/Neo4j/HTTP stopped, storage preserved, exclusive binds pass on
16333/16334/17687/18108. Foreign workloads remain untouched.
