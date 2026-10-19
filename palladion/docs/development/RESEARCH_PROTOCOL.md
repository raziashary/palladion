# Research and later comparison protocol

Current checkpoint2026-10-19: P06 published6444345; P07 graph and owner-added automatic memory implementation, consumer proof and sole LunaMedium end-review resolution verified (E-P07-001/002). ADR0063–0066 owner approvals preserved. Graph stays off after zero incremental recoveries. P08/UI/benchmark edits and another main push remain excluded. Older phase snapshots below are historical.

Status: **P02 retrieval-only pilot recorded; P05 continuity and P06 critic pilots recorded with failures; no confirmatory answer-system experiment executed**. Governing source: blueprint “Research
evaluation,” “Questions deliberately left to experiments,” “Prototype environment.”
Research records follow [ADR-0007](ADR_LOG.md#adr-0007--research-discipline-and-gate-meanings).
Protocol metrics are intended measurements; recorded pilot sections identify actual observations and limits.

## Question and falsifiable hypotheses

Can this bounded evidence-first harness reduce unsupported answers over simpler RAG
without unacceptable latency, cost, excessive abstention or lost investigation usefulness?

| Hypothesis | Treatment / control | Evidence against the hypothesis |
|---|---|---|
| H01: hybrid discovery helps | B1 vs B0, fixed corpus/model/scope | Recall or downstream support unchanged/worse, or costs exceed frozen tradeoff target |
| H02: context/reranking finds exceptions | B2 vs B1 | Exception recall/support unchanged or valid sources displaced |
| H03: time-aware policy prevents invalid directives | B4 vs declared B2 or B3 parent, otherwise fixed | Temporal failures/unsupported actions persist or false vetoes erase useful decisions |
| H04: structured continuity preserves state safely | B5 vs B4 on multi-turn cases | Omission, stale evidence, scope leakage or anchoring increases; task completion does not improve |
| H05: critic corrects additional errors | B6 vs B5 using same saved draft and initial ledger | No incremental corrections, unsupported challenges/false vetoes, or disproportionate cost |
| H06: graph earns its complexity | B3 vs B2 fixed retrieval queries | No incremental gold-clause recovery, identity contamination, or maintenance/cost outweigh gain |
| H07: adaptive review can retain critical detection | B7 vs always-on B6 after risk labels collected | Important false skips, worse action support or savings below frozen target |
| H08: planner/fusion/vector memory are worth adding | B8/B9 and isolated memory-vector arm vs exact declared parent | No measurable benefit after accounting for added work and reliability risks |

The Q08 method is accepted in ADR-0019; actual numerical targets and sampling require
development evidence. Derive effect sizes and budgets from B0/B1
development data, then preregister numerical criteria before held-out runs. Until then,
these hypotheses have direction and instruments but no invented success threshold.

## Selected runtime and approved setup

ADR-0013 selects uv (`uv venv` in `C:/palladion/palladion`, app-local `.venv`, pinned
`uv.lock`) and real Groq `qwen/qwen3.8-27b` for initial generative runs. Main and critic
use separate contexts; a shared provider/model is not independent truth. Runtime choice
does not constrain development subagents, which remain GPT 6 Luna Medium, or prescribe
an embedding model. Actual embedding/tokenizer selection follows the compatibility task.

P01 package setup is authorized and deterministic foundation fixtures are validated;
no model experiment or research result exists. The corpus remains PILOT without two
independent human annotators/adjudication. P01 makes no provider request.
After GO, run enabled provider experiments under explicit quotas/call/token/time budgets,
record actual model ID and structured/tool behavior, and load only the existing root
`.env` for the specific command. No fake runtime result may replace failed model proof.
Deterministic scorer/guard input fixtures remain distinct from actual model outputs.

The [Groq model page](https://console.groq.com/docs/model/qwen/qwen3.8-27b) lists the
selected model, and [free-plan rate limits](https://console.groq.com/docs/rate-limits)
are documented (checked 2026-10-17). This does not verify account access or unlimited
capacity. Report actual billing if any, zero billed only when evidenced, and separately
estimated list-price resource cost if useful; never assume all inference is cost-free.

## Internal treatments B0–B9

| Arm | Definition from blueprint | Control and caution |
|---|---|---|
| B0 | BM25 + exact identifiers + one LLM | Lexical reference; same canonical corpus/ACL |
| B1 | Dense ANN + BM25 native RRF + exact + one LLM | B0, same generation model and question set |
| B2 | B1 + reranker + parent context | B1; record actual rerank/expanded passage budgets |
| B3 | B2 + bounded Neo4j source expansion | B2; record extraction/review and query cost |
| B4 | B2 **or** B3 + deterministic time-aware policy | Declare chosen parent for each run; never pool the two silently |
| B5 | B4 + typed scoped memory and continuity | Same multi-turn script, corrections and evolving observations |
| B6 | B5 + always-on critic | Saved-draft paired and full end-to-end analyses separately |
| B7 | B5 + risk-triggered critic | Later experimental treatment; not default normative release path |
| B8 | B5/B6 + optional small-model nonexclusive planner | Declare parent; planner call counted (up to 9 calls per blueprint variant) |
| B9 | Fixed B2 data, native RRF vs controlled alternative fusion | Exactly one dense/sparse fusion stage per treatment |

P02 records retrieval-only lexical/hybrid/reranked-context substrate pilots, not full
B0/B1/B2 arms (those include generation). No answer-quality conclusion is possible at
P02. Preserve language/time/ACL slices and index-state disclosures. Full treatments mature later. B3's label
does not require implementing graph before policy/memory/critic; follow the build slices.
Vector memory compares structured/FTS-only against vector augmentation as a separately
named treatment, not an undisclosed change to B5.

Comparative runs with critic disabled or deterministic safeguards ablated execute in an
isolated synthetic evaluator. Their raw answers are scored as experimental artifacts,
not released as supported operational guidance. If a common safety wrapper is imposed,
retain and score both raw and wrapped results; disclose its effect rather than giving
baselines hidden Palladion capabilities. Never disable real authorization for a benchmark.

## Recorded P02 substrate pilot

E-P02-001 records the actual eight-case/two-profile run, raw artifact hash and metric
denominators. Both BM25 profiles tied here; lexical MRR0.9, hybrid/reranked/context MRR1.0,
Recall@5=1.0 on the scored tiny cases. Reranking showed no added quality on this pilot.
These are descriptive pilot measurements, not full B0/B1/B2 answers or a general winner.
The corpus is English; one of eight queries is Indonesian. Human adjudication, meaningful
sample size, held-out results and overall hypothesis conclusions remain unexecuted.

## Corpus, splits and labeling

Use synthetic internally consistent SOPs, versions, exception appendices, drafts, policies,
roles/cases, timestamps and mock observations. Preserve T01–T24 and source inventory tests.
Separate intentionally absent external inventory from accepted-but-unindexed sources and
from inaccessible sources; they test different failure mechanisms.

Before a meaningful research claim:

1. Define corpus/version hash, case-family IDs, language/time/ACL/difficulty strata and
   annotation schema. Every golden identifies admissible exact clauses, applicable rule
   version/time basis, required facts, expected outcome/disposition, forbidden actions,
   allowed hypotheses and evaluator notes.
2. Have at least two annotators review gold labels; log disagreement, adjudicator,
   rationale and remaining ambiguity. LLM agreement is not a substitute. If independent
   human labels are unavailable, report pilot-only evidence and keep the limitation visible.
3. Split development/calibration/held-out by case/document family to prevent near-duplicate
   policy revisions or reworded cases leaking across splits. Freeze split manifest and seed.
4. Decide sample size, repeated generations, randomization, uncertainty method and numerical
   targets using development observations. Record them before held-out execution.
5. Freeze a deterministic retrieval benchmark and repeat stochastic generation per plan.
   Persist actual responses/tool traces; a seed alone may not reproduce a hosted model.

Do not tune prompts, thresholds, chunking or risk rules on the final held-out cases. A
post-result fix requires a new version/run and fresh held-out evidence for a fresh claim.

## Metric definitions and honest denominators

| Dimension | Required measurement |
|---|---|
| Retrieval | Gold admissible clause Recall@5/10/20; nDCG@K with declared relevance grades; MRR; exact-ID hit rate; exception recall; ANN-vs-exact dense neighbor recall. Report candidate, fused, reranked and expanded stages and actual HNSW/exact index state. |
| Authority | Resolvable exact-span citations / all emitted citations; support precision = semantically supported cited claim associations / adjudicated cited associations; approved/applicable source rate; temporal version accuracy; completed provenance chains. |
| Answer integrity | Unsupported material claims / adjudicated material claims; answers with any unsupported material claim / scored answers; unsupported operational actions / adjudicated action claims, plus count of cases with any unsupported action. Hallucinated citation counts/rate. |
| Qualification | Expected-disposition accuracy; abstention precision/recall against gold answerability; required missing-slot recall; contradiction detection; safely labeled hypotheses / hypothesis statements; false vetoes of gold-supported claims/answers. |
| Utility | Human-rated investigation usefulness using a frozen rubric; supported answer coverage on answerable cases; task completion and omission across continuations. A refusal-only system cannot win on unsupported rate alone. |
| Operations | p50/p95 end-to-end and component latency with sample size; main/critic/planner calls, initial/counter searches, tools, retries, tokens, cache hits, exhausted budgets and wall time; actual or explicitly estimated cost. |
| Safety | Attempt counts and observed leaks/side effects for tenant/case/role/graph/memory/tool injection tests; source freshness/schema errors; index lag; graph fan-out and identity failures. |

Zero denominator is `N/A` with numerator/denominator, not 0% or 100%. Report raw counts,
missing/failed runs, case-level paired differences and uncertainty intervals appropriate to
the preregistered design. Cluster repeated outputs by case when estimating uncertainty;
repetitions are not independent new cases. Include language, temporal, ACL, difficulty and
question-type breakdowns so an aggregate does not hide an exception failure.

Model/scorer identity, prompts and limitations must be disclosed for any auxiliary LLM
judge. Deterministic checks and independent annotations own integrity/support labels;
the answering model never grades itself as sole truth.

## Critic-specific controls

Freeze question, draft and initial evidence ledger. Evaluate reviewer off/on on that pair.
Separate (a) same-context review, (b) review with independently authorized counter-search,
and (c) optional blind-requirements prepass. Count corrections, false objections/vetoes,
misses, changed evidence, extra calls/tokens/time and useful next steps. Then run the
full live orchestration as a different experiment; different end-to-end traces alone
cannot isolate the critic's contribution. Test the withheld-appendix shared blind spot.

## Future external comparisons in baseline/

X01 remains deferred. Define exact standard RAG pipeline, LangChain-based pipeline and
named provider system/version before implementation; LangChain is a library, not a
single retrieval architecture. Keep each adapter and dependencies isolated under the
reserved sibling directory. Do not assume provider systems expose policy, live state,
memory, citations, or equal control over model/budgets.

Use a shared evaluator input/output contract that includes case/scope, supplied corpus,
observations, query, result claims/citations/disposition where available, timing and
resource ledger. This contract is planned, not an existing API. Reject unsupported
feature assumptions; capability differences are recorded before scoring.

Run two clearly labeled tracks when needed:

- **Matched capability/resource track:** same eligible documents, principal scopes,
  model/prompt where possible, comparable retrieval/passages/tools/call/time budget,
  common scenario and fixed synthetic observations. Compare only supported capabilities.
- **Native configured system track:** each system's documented configuration and actual
  abilities, with all differences/costs reported. Do not attribute the full difference
  solely to the harness architecture or hide additional tools/data/model calls.

Include document-only tasks where all systems can compete. For policy/live/continuity
tasks, report capability gaps and safety of handling them rather than penalizing a
document-only baseline for not possessing hidden inputs. `N/A` differs from incorrect.
Freeze tuning effort and corpus access, randomize execution order, declare warm/cold
caches, concurrency and hardware. Include ingest/index/model hosting and maintenance
cost separately from per-query cost; critic searches are never free or hidden.

No overall scalar score now. If later requested, preregister dimensions/weights and show
raw metrics and sensitivity to weights. Preserve neutral and negative results. Do not
pick only best-of-N runs or omit failed/provider-timeout cases from denominators.

## Required run artifact and report

Each future run records: run ID/UTC date; git revision plus dirty patch hash; treatment
and parent; corpus/gold/split hashes and annotators; principal scope digest; pinned model,
embedding/tokenizer, dependencies, prompts and schema versions; configs/budgets/flags;
source/index generations; hardware/concurrency/cache state; randomness/repetition plan;
actual outputs, evidence handles and sanitized traces; raw counts, costs, latency samples
and failed runs; scorer/version/rubric; exclusions and reasons; conclusions and limitations.

Keep small redacted manifests/summaries and their artifact hashes/paths referenced from
EVIDENCE_LOG. Large raw outputs stay outside commits in a declared artifact location;
do not commit secrets, private data or giant generated reports. A report without accessible
underlying artifacts is an evidence gap. Label the failure-owning stage: ingestion,
candidates, ranking, source resolver, tool selection, policy inputs, critic, gate or scoring.

## P03 domain verification boundary

E-P03-001 verifies deterministic temporal rules and scoped mock observations, not a full
B4 answer arm. No generative model/provider call, answer-quality score, human adjudication
or baseline superiority is inferred. Mock operation freshness/deadline limits are synthetic
owner assumptions (ADR-0029), not measured business thresholds. Knowledge-cutoff audit is
minimal registry reconstruction; input observation read times and actual evaluated-at remain
explicit. Preserve current versus audit-mode outcomes and source/target-denial failures.

## P04 runtime transport scope

E-P04-001 contains actual selected Groq transport/HTTP/domain checks. These remain
engineering smokes with PILOT fixtures, not an adjudicated B4 arm or quality estimate.
Retain quota/transport/schema failures and all attempts. Human semantic support labels
and escalation assignee remain unavailable; operational permission is not supported
before P06 mandatory review. Current exact attribution/typed fact rubric is ADR-0033.

P04 engineering results cover actual five dispositions and document citation consumers
across explicit owner-approved Qwen/GPT-OSS120B/20B selections, including exact-wheel
and real TCP entry points. These are path checks, not a success-rate sample: retain every
failed run/model/attempt, do not turn selected passing reruns into model comparisons.
Provider tokenizer revision is not disclosed here; actual provider token counts are
recorded, without cross-model tokenizer equivalence claims. No benchmark dataset,
license, arm implementation or confirmatory-run decision is supplied by this phase.


## P05 fixed continuity pilot

ADR-0041 fixes one synthetic case, B4 parent=B2+policy (reranker enabled, graph off),
B5 memory on and B5 compressed1500 vs6000 characters, identical saved history and
current mock snapshots, no critic/vector. data/demo/retrieval_pilot.json pins conditions.
`evaluate.py --run --memory --enable-live-llm --model <approved-model>` saves every
raw API response/packet/received usage/budget/error/rate header and citation readback
under a fresh run ID. Forty unrelated turns stress continuity. First stateFAILED,
second statePENDING; settlement_state remains missing. Exact scorer reports packet
and answer gap omissions, stale controlled claims, fresh-state release and strict
completion (provider failures make completionfalse), with explicit denominators.
B4 withholds packet/recall through explicit evaluator settings; four tool names and
canonical authority/gate remain unchanged. Initial setup must actually retain the
critical gap; failed setup is disclosed, never fabricated. Each condition waits45s
between requests and has at most5 main calls,8tools,60s; no failed condition retries
inside a run. Lifecycle reruns retain originals. Character bounds are not token counts;
actual received provider usage is separate, missing values are not zero. A CLI exit0
means all conditions were observed and resources closed, not that models passed or
H04 succeeded. No human-adjudicated semantic usefulness or held-out inference.

## P06 frozen critic pilot preparation

ADR0046 is owner-approved. First actual pilot is retained with its fixture confound
and full-runtime provider failure; v2 completed all16conditions (E-P06-001). Use a versioned critic_pilot fixture
manifest with controlled draft templates and explicit mechanical expectations; never
label synthetic initial mistakes as measured main-model error rates. Bind logical
fixture IDs to canonical authorized sources, then freeze question, draft, initial ledger,
requirements, source generation and context once per case. Persist/read back and hash
that envelope; off/fixed-context/counter-search/blind-requirements readers must report
equal initial hashes. Changed admissible evidence and finalization outputs are separate
artifacts. A withheld appendix must actually be absent from the supplied registry/index,
not merely revoked/inaccessible; no inventory-completeness claim is permitted.
Record real review/final outputs and shared tool/call/time costs, unknown token usage
as unknown, rejected fabricated objections and every failed arm. Actual full-runtime
Groq message runs are separate from controlled frozen-draft pairs. No human labels or
semantic adequacy are invented, and no narrower check stands in for the phase exit.

ADR0050 corrects the scorer's former omission-as-veto label. Original scores stay
unchanged in their launch-version artifacts. Scorer2 derived summaries report known
fact retention loss and structured false objections independently; causal critic veto
and unadjudicated semantic outcomes remain null. Strict full-clause quote misses are
not converted to successes when a shorter valid excerpt is present. ADR0051's explicit
full-message engineering probe is distinct from all frozen paired denominators.

V2 recorded16main/23critic/6counter-search attempts and72163received tokens across
all16conditions, excluding its separate full-message row. Three review conditions
retain schema failures; known fact retention15/16, with one loss relative to off and
zero known-control false objections in valid parsed reviews. Causal/semantic false
veto rates remain unknown. Strict full-delay-clause quote correction0/4; two exception
search conditions discovered new appendix and released exact boundary excerpts.
The experiment does not show an accuracy gain or justify adaptive critic skipping.
Retain mandatory normative review during prototype evaluation per the blueprint;
optional blind/counter variants remain explicitly measured treatments. Full-message
400/429 failures remain retained; ADR0053 pacing is owner-approved. Default20B/120B
now verify real review/final/readback but not critic discovery (main fetched appendix).
The lower-cap recovery scenario is a separate engineering condition, not a frozen
research treatment or replacement for the default-budget generated-draft proof.

Owner approved ADR0053 via async reply2026-10-19 (supersedes earlier pending
checkpoint text). Opt-in model-call pacing defaults0 and is now implemented, with
post-wait caller authorization/evidence validation. Focused98checksPASS15.51s;
actual paced message proof, complete gates and sole end audit remain pending.
ADR0054 strengthens pre/post critic discovery attribution and safe attempt diagnostics.

## P06 final-source paired receipt — 2026-10-19

All six P06 atomic task proofs are verified; the sole Luna Medium end reviewer has
resolved R1 and withdrawn R2 (E-P06-002). Phase closure awaits post-fix final gates,
docs, owned cleanup and a scoped local commit. Pre-audit source290 + actual-Qdrant13 =303 disjoint checks passed; installed290 and one
installed actual-Qdrant/API control overlap. All50 packaged files match the wheel.
Owner-approved ADR0045/0046/0053 govern; no P06 main push or P07 GO is inferred.

Real20B strict exact-ID recovery passes31.076s (explicit maincap2,2main/2critic/1search,
SAFE_TEMPLATE initial); default-budget generated-draft path passes47.949s (4main/1critic,
MODEL initial). Both release the full canonical exception with citation/timeline readback
and no verification failures. They prove distinct engineering paths, not reliability.

Final-source20B paired report p06-cb9e66c994dc46b9b0746c7b92c644fd records16/16 observed
conditions, equal frozen hashes,16/16 known-fact retention,0/4 full exception corrections,
one critic validation failure,16main/17critic/4searches and66117 known received tokens.
One attempt lacks usage; totals are lower bounds. Blind requirements discovers new
appendix evidence but does not release its full clause. Ordinary counter-search-enabled
review never requests a search in these four cases. No efficacy gain is established;
retain mandatory review under the existing architecture without adaptive/default changes.
Semantic accuracy, causal false-veto and H05 remain unknown; P08 owns adjudication.
Older120B reports remain versioned historical measurements, not final-source results.

Command: `.venv/Scripts/python scripts/evaluate.py --run --critic --enable-live-llm
--model openai/gpt-oss-20b --model-call-interval 0` exited0: observation completion and
cleanup, not model success. Raw SHA256
`c0fa225c5991f75eec61ce5eb29e36b5e1b5e75bd2b299835e7f37b3546e9d7f`;
raw-preserving scorer2 summary SHA256
`6d944a9b2703f11a54c5427cf46bd89a353c16f93c61d39a565a9f4352f3a681`.
Both reside in ignored `runtime/evaluation/` under the report stem above. Automatic
same-stem launch snapshot hashes verify; source hashes showed zero drift before the qualification-only ADR0062 gate correction.
Derivation: `.venv/Scripts/python runtime/p06_derive_summary.py
runtime/evaluation/p06-cb9e66c994dc46b9b0746c7b92c644fd.json`; raw bytes unchanged.

| Arm (four cases each) | Main/critic/search | Known received tokens | Median/max seconds |
|---|---|---|---|
| off |4/0/0|7279 (one missing usage)|1.255/1.721|
| fixed_context |4/4/0|16018|2.212/2.715|
| counter_search |4/5/0|18105|2.155/3.770|
| blind_requirements |4/8/4|24715|10.541/14.219|

Counter_search/missing_inputs records CRITIC_SCHEMA_OR_GROUNDING_FAILURE and retains
settlement_state plus mandatory review gaps. All four missing-input arms retain
settlement_state. Withheld inventory remains unattested in every arm; some blind outputs
have no explicit missing requirement, which cannot establish completeness. No known-valid
parsed claim is falsely challenged by the mechanical classifier; semantic/causal scores
remain unknown. Ordinary fixed/counter critics mark controlled invalid C2 supported in
exception/withheld cases; blind conditions detect three C2 invalid associations. These
misses remain visible: critic agreement is not independent ground truth.
Full-runtime row returns200/PASS,4main/1critic, resolved citations/no verification failures,
but omits the full exception. It cannot replace separate strict normal/recovery proofs.
External60s arm spacing, intra0, original freshness/deadline and no retries/fallback are
recorded. Models are not compared for quality across source versions.

Actual-Qdrant exact coverage guard later passes1test39.05s (18deselected),
`runtime/p06-coverage-actual-server.log`: coverage false before exact lookup, true after
new canonical evidence; protected data absent in timeline. This overlaps303, not an added
independent check. Production source stayed frozen. Sole end review now dispatched.

P06 arm clarification: blind_requirements is draft-blind first-pass review under
blueprint §10.1; canonical policy-required slots remain supplied. It does not measure
independent discovery of unsupplied requirements. End-review R2 is withdrawn.

End-review R1 confirmed: ADR0062 qualifies changed final proposals and unresolved
CHALLENGE without erasing canonical facts. Final matrix cb9e66 remains its unchanged
model/prompt/launch-gate version; qualification-only gate correction follows it. Quote,
fact-retention and model-cost observations are not relabeled as post-correction outputs.
Post-fix stack/installed/live checks and same-reviewer resolution precede closure.

## P06 closeout interpretation

P06 DONE at E-P06-001/E-P06-002: all six atomic cards, approved critic/status/pacing
contracts, actual source/installed/API consumers and sole Luna Medium end-review
resolution are verified. Source294PASS plus13 actual-Qdrant cases pass (12 in the sweep,
one isolated after a setup connection-abort) =307 disjoint checks. Installed294 and one
installed real-Qdrant/API case pass as overlapping artifact checks; all50 packaged files
match the final wheel. Ruff, strict mypy59, dependency81+4controls, foundation CLI and
final document gates pass. Original failed/skipped runs remain evidence, not PASS.

Post-fix real20B exact recoveryPASS39.827s (2main/2critic/1search, explicit cap2) and
serialized default-budget MODEL-draft pathPASS37.089s (4main/1critic/2tools) release the
full exception with original citation/timeline readback and no verification errors.
Gate qualifies a changed final proposal or unresolved CHALLENGE while preserving
canonical facts; unchanged current PASS remains eligible for SUPPORTED. Model review
is advisory, not semantic authority or payment permission.

Frozen prompt-version20B matrix cb9e66:16conditions,16/16known-fact retention,
0/4full-exception corrections, one critic validation failure,16main/17critic/4searches,
66117known received tokens (one attempt lacks usage). It precedes ADR0062's gate-only
qualification fix: no model prompt changed; raw outputs are not relabeled post-fix.
No efficacy/H05, semantic accuracy, causal false-veto or completeness claim. Mandatory
review remains enabled; draft-blind first pass sees canonical required slots (§10.1).
At the historical P06 checkpoint, P07 graph/P08 adjudicated research/X01 comparators remained deferred; no P07 GO or P06
main push is inferred. No unanswered P06 owner ADR. Owned processes stopped, storage
preserved and ports16333/16334/18080 verified free; foreign benchmark/editor work untouched.

## P07 automatic promotion pilot protocol (owner amendment ADR0066)

Freeze synthetic event chunks, exact event/span hashes and labeled examples before comparison. Compare primary deterministic PathA with A+optional local cosine/loss PathB under identical sessions/users/source scope. Record category decisions, hard-rule results, cosine scores, margin loss, weighting/config/model fingerprints, abstentions, false global promotion, procedural authority escapes, latency/calls and retained/disabled choice. Deterministic eligibility/ACL rejection is invariant, not a score that similarity can outvote. Similarity is not truth and a loss formula is not evidence of trained/calibrated classification. Actual local encoder and actual message memory-reader checks are separate from injected controls. All uncertain or failed decisions stay episodic; source/case revocation still applies. No embedding store or Groq classifier is implied. Human-adjudicated generalization stays P08.

## P07 observed development pilots (E-P07-002)

Versioned graph pilot CLI is scripts/evaluate_graph.py, separate from P02/P05/P06 scripts/evaluate.py. Run00c4866d27684be6bcd701831448256f preserves4paired inputs under identical source/index/ranker/scope/top4 conditions. Both arms recover2expected appendices;0incremental recoveries. Unknown-ID negative preserved. Graph default stays disabled. B2 already has the registered context link; a separate injected-anchor two-hop control proves navigation, not incremental semantic recall. Raw percondition timings and failures are retained; one ordered tiny development run does not support throughput, tails, generalization or superiority. Graph-required verification failure is unavailable; optional failure is explicit degradation.

Memory corpus data/demo/memory_promotion_pilot.json SHA25639cea5a9ad1f7d5c9b6c395d13f10e8267a3cfe119715067130c40a12fcdbff4 freezes6queries before the run:4mechanical scope/category controls,2unknown nonprototype semantic labels. Rules plus optional actual local encoder make1call/12texts/0Groq,5.91seconds;4mechanical controls pass and both unknown cues remain episodic. One is ineligible under frozen rules, one misses cosine/combined thresholds. This is not4/4semantic accuracy. Positive prototype-identical integration control is reported separately, never treated as generalization. Weight.8/threshold.75/margin.1/combined.65 and loss formula remain untrained/uncalibrated, with full profile and model/prototype fingerprint persisted.

Real20B next-session consumer test00c4866d receives auto-stored preference and excludes old episodic canary; canonical source/tool release remains authority-controlled. All10model invocations receive responses, bounded main/critic/tool counts and rate-limit headers preserved. This proves context wiring only. P08 human adjudication, held-out outcomes and external comparisons remain prerequisites for hypothesis/accuracy claims.


## P07 final phase-local disposition (2026-10-19)

E-P07-002 records all11cards, actual source/installed/CLI/provider and original-reader proof, the sole GPT6LunaMedium end audit and same-reviewer resolution. The reviewer read the full blueprint (§1–§18), I01–I15, graph and memory amendment; three current-facing document contradictions were fixed and rechecked. No confirmed source defect remained. Graph has0incremental recoveries in4paired queries and stays off by default; controlled path recovery proves integration only. PathA automatic promotion and opt-in bounded local PathB retain original ACL/authorityNONE;4mechanical pilot labels pass,2semantic labels remain unknown. Historical failures and intermediate pending statuses above remain dated snapshots, not current scope. No unanswered P07 owner ADR; P08 adjudication, generalization and external comparisons remain excluded.
