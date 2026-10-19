# P08 proposed final synthetic pilot protocol

Status: APPROVED by explicit owner async answer,2026-10-19: "Approve protocol and
estimated-token ceiling (Recommended)". Machine freeze binds the final configuration.

Development calibration is preserved in four unique runtime/evaluation directories.
Latest rich-source run: `p08_caba76ebfdc344c9b7dbf31abc729d45`, study SHA256
`426dce1764541bcd862e856fc08221d5e94c821c48d885be3c5c15cfe224d8ba`.
All8provider calls received responses. B0 parsed4/4; B1 parsed2/4, with2Draft
validation failures. Both arms recovered the exact quote in2/4 attempted observations;
wrapped disposition matched SUPPORTED in0/4. Failed parses remain in denominators.
B0 p50/p95 elapsed9.444/9.772seconds; B1 10.260/10.831seconds. These tiny-sample
figures include configured spacing and do not establish capacity or semantic quality.
Collection readback reports12points/12indexedvectors; no HNSW speed claim follows.

## Proposed freeze

- Two separate, family-disjoint synthetic evaluation cases, English and Indonesian;
  original current, retired, draft and restricted documents, predeclared exact quotes.
- Eleven arms: B0–B9 plus B5_VECTOR; two repetitions each,44observations, shuffled
  seed1719. Same explicit Groq openai/gpt-oss-20b,temperature0.2,provider seed unknown.
- Normal5main/3critic/8tools/60seconds per runtime request; B8 may add1planner call.
  Configured10second model spacing remains inside deadlines. No retry/fallback.
- Run caps200model attempts/7200seconds. Approved raising the conservative run-wide
  estimated-token cap from160000 to2000000 so it can cover the full planned grid;
  this is a safety ceiling, not a promise to consume it or a billable-token estimate.
  Actual received usage, missing usage, quota failures and prevented attempts stay distinct.
- Mechanical development-derived targets: at least0.5exact-quote recovery per full
  arm (development baseline0.5);100%resolvability of released citations;0restricted
  canary leakage in the declared controls; no exceeded request/call/tool budgets.
  Targets are assessed, never forced by relabeling or deleting failures. Null/adverse
  results do not make the implementation incomplete if all required checks are executed
  and failures correctly preserved; unresolved correctness/security defects do.
- Compare B7 to B6, B8 to B6, B5_VECTOR to B5; report all-attempt latency/call/token
  differences with case-clustered uncertainty. Two clusters cannot support generalization.
- Semantic support, human usefulness, unsupported-material/action accuracy and causal
  false-veto remain UNKNOWN without independent human adjudication. This is a synthetic
  pilot, not a confirmatory held-out result, H01–H05 success or baseline superiority.
- Existing T01–T24 remain separately executed regression/fault controls; dataset slices
  without observations are NOT_APPLICABLE, not inferred successes. Serving defaults stay
  unchanged. Graph remains off except explicit B3 treatment.

On approval, write immutable machine protocol with final study hash and exact calibration
artifact digests before starting the evaluation grid. Source snapshots, raw calls,
originals, manifests, rows and failures are retained locally; public report is redacted.

Approved machine freeze: [p08-approved-protocol.json](p08-approved-protocol.json).
Final configuration hash (only approved estimated-token ceiling differs from R3):
`987e3773fd6b0a1938d54c1e1903647d2e187e41142a9e7b05d05db2f29ce390`.

## My answer (editable)

Approve protocol and estimated-token ceiling (Recommended).
